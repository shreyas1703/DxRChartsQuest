// Runs the real DxR port (Parser → Mark.Infer → scales → marks → axes → legend) headlessly and dumps geometry.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using UnityEngine;

class Harness
{
    static string F(float v) { return v.ToString("0.#####", CultureInfo.InvariantCulture); }
    static string V(Vector3 v) { return "[" + F(v.x) + "," + F(v.y) + "," + F(v.z) + "]"; }
    static string C(Color c) { return "\"#" + ColorUtility.ToHtmlStringRGB(c) + "\""; }
    static string Q(string s) { return "\"" + (s ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n") + "\""; }
    static object Get(object o, string f) { return o.GetType().GetField(f, BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public).GetValue(o); }

    static int Main(string[] args)
    {
        string charts = args[0], resources = args[1], outDir = args[2];
        CultureInfo.DefaultThreadCurrentCulture = CultureInfo.InvariantCulture;
        CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
        Application.streamingAssetsPath = charts;
        UnityEngine.Resources.Root = resources;
        Directory.CreateDirectory(outDir);
        var list = DxRSimpleJSON.JSON.Parse(File.ReadAllText(Path.Combine(charts, "DxRSpecs/charts.json")));
        int fails = 0;
        foreach (DxRSimpleJSON.JSONNode c in list["charts"].Children)
        {
            string spec = c["spec"].Value;
            try
            {
                var go = new GameObject("vis");
                var vis = go.AddComponent<DxR.Vis>();
                vis.Load(spec);
                var sb = new StringBuilder("{");
                sb.Append("\"spec\":").Append(Q(spec)).Append(",\"title\":").Append(Q(vis.Title));
                sb.Append(",\"size_m\":").Append(V(vis.GetVisSize() * DxR.Vis.SIZE_UNIT_SCALE_FACTOR));
                sb.Append(",\"marks\":[");
                bool first = true;
                foreach (var m in vis.markInstances)
                {
                    var mark = m.GetComponent<DxR.Mark>();
                    var r = m.GetComponent<Renderer>();
                    if (!first) sb.Append(","); first = false;
                    sb.Append("{\"kind\":").Append(Q(mark.markName)).Append(",\"color\":").Append(C(r.material.color));
                    if (mark is DxR.MarkArc)
                    {
                        sb.Append(",\"center\":").Append(V(m.transform.position));
                        foreach (var k in new[] { "startDeg", "endDeg", "radiusMm", "thicknessMm" }) sb.Append(",\"" + k + "\":").Append(F((float)Get(mark, k)));
                        var mesh = m.GetComponent<MeshFilter>().sharedMesh;
                        sb.Append(",\"verts\":").Append(mesh.verts.Count).Append(",\"tris\":").Append(mesh.tris.Count / 3);
                    }
                    else
                    {
                        var b = r.bounds;
                        sb.Append(",\"min\":").Append(V(b.min)).Append(",\"max\":").Append(V(b.max));
                    }
                    var lo = Get(mark, "labelObject") as VLMCharts.TextLabel;
                    if (lo != null) sb.Append(",\"label\":").Append(Q(lo.text)).Append(",\"label_pos\":").Append(V(lo.transform.position));
                    var datum = new List<string>();
                    foreach (var kv in mark.datum) datum.Add(Q(kv.Key) + ":" + Q(kv.Value));
                    sb.Append(",\"datum\":{").Append(string.Join(",", datum.ToArray())).Append("}}");
                }
                sb.Append("],\"texts\":[");
                first = true;
                foreach (var t in AllLabels(go.transform))
                {
                    if (!first) sb.Append(","); first = false;
                    sb.Append("{\"text\":").Append(Q(t.text)).Append(",\"pos\":").Append(V(t.transform.position))
                      .Append(",\"h\":").Append(F(t.height)).Append(",\"align\":").Append(Q(t.align.ToString())).Append(",\"roll\":").Append(F(t.roll))
                      .Append(",\"color\":").Append(C(t.color)).Append(",\"name\":").Append(Q(t.gameObject.name)).Append("}");
                }
                sb.Append("],\"lines\":[");
                first = true;
                foreach (var l in AllLines(go.transform))
                {
                    if (!first) sb.Append(","); first = false;
                    var r = l.GetComponent<Renderer>();
                    sb.Append("{\"name\":").Append(Q(l.gameObject.name)).Append(",\"a\":").Append(V(l.TransformPoint(new Vector3(0, 0, -0.5f)))).Append(",\"b\":").Append(V(l.TransformPoint(new Vector3(0, 0, 0.5f))))
                      .Append(",\"color\":").Append(C(r.sharedMaterial.color)).Append("}");
                }
                sb.Append("],\"swatches\":[");
                first = true;
                foreach (var w in AllSwatches(go.transform))
                {
                    if (!first) sb.Append(","); first = false;
                    var r = w.GetComponent<Renderer>();
                    sb.Append("{\"name\":").Append(Q(w.gameObject.name)).Append(",\"min\":").Append(V(r.bounds.min)).Append(",\"max\":").Append(V(r.bounds.max))
                      .Append(",\"color\":").Append(C(r.sharedMaterial.color))
                      .Append(",\"sphere\":").Append(w.GetComponent<MeshFilter>().sharedMesh == VLMCharts.Prims.SphereMesh ? "true" : "false").Append("}");
                }
                sb.Append("]}");
                File.WriteAllText(Path.Combine(outDir, Path.GetFileNameWithoutExtension(spec) + ".json"), sb.ToString());
                Console.WriteLine("OK   " + spec + "  marks=" + vis.GetNumMarkInstances() + "  inferred encoding keys=" + vis.InferredSpecs["encoding"].Count);
                File.WriteAllText(Path.Combine(outDir, Path.GetFileNameWithoutExtension(spec) + ".inferred.json"), vis.InferredSpecs.ToString(2));
            }
            catch (Exception e) { fails++; Console.WriteLine("FAIL " + spec + "\n" + e); }
        }
        return fails;
    }

    static IEnumerable<VLMCharts.TextLabel> AllLabels(Transform t)
    {
        foreach (var c in t.gameObject.components) if (c is VLMCharts.TextLabel && !c.destroyed) yield return (VLMCharts.TextLabel)c;
        foreach (Transform ch in t) foreach (var x in AllLabels(ch)) yield return x;
    }

    static IEnumerable<Transform> AllLines(Transform t)
    {
        string n = t.gameObject.name;
        if (n == "AxisLine" || n == "Tick" || n == "Grid" || n.StartsWith("DataLine")) yield return t;
        foreach (Transform ch in t) foreach (var x in AllLines(ch)) yield return x;
    }

    static IEnumerable<Transform> AllSwatches(Transform t)
    {
        string n = t.gameObject.name;
        if (n.StartsWith("Swatch") || n == "GradientCell") yield return t;
        foreach (Transform ch in t) foreach (var x in AllSwatches(ch)) yield return x;
    }
}
