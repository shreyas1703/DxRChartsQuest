using System.Collections.Generic;
using UnityEngine;

namespace VLMCharts
{
    /// <summary>
    /// Replaces DxR's Resources/Marks/&lt;name&gt;/&lt;name&gt;.prefab lookup with procedurally built,
    /// inactive template objects (no HoloToolkit prefabs, no asset files needed).
    ///   bar    — unit cube + DxR MarkBar (sizes grow from the base, like DxR's bar mark)
    ///   cube   — unit cube + DxR Mark
    ///   sphere — unit sphere + DxR Mark   (alias: point)
    ///   arc    — pie/donut slice + DxR MarkArc (new)
    ///   line   — sphere at every data point; Vis joins the points of each colour series with line segments (new)
    ///   rect   — unit cube (heatmap cell: x/y band position, width/height/depth from the spec)
    /// </summary>
    public static class MarkFactory
    {
        static Transform _root;
        static readonly Dictionary<string, GameObject> Templates = new Dictionary<string, GameObject>();
        public static readonly string[] Supported = { "bar", "cube", "rect", "sphere", "point", "line", "arc" };

        public static GameObject GetTemplate(string markName)
        {
            string name = (markName ?? "").Trim().ToLowerInvariant();
            GameObject t;
            if (Templates.TryGetValue(name, out t) && t != null) return t;
            if (_root == null)
            {
                var r = new GameObject("DxR mark templates");
                r.SetActive(false);
                Object.DontDestroyOnLoad(r);
                _root = r.transform;
            }
            switch (name)
            {
                case "bar": t = Make(name, Prims.CubeMesh, typeof(DxR.MarkBar)); break;
                case "cube":
                case "rect": t = Make(name, Prims.CubeMesh, typeof(DxR.Mark)); break;
                case "sphere":
                case "point":
                case "line": t = Make(name, Prims.SphereMesh, typeof(DxR.Mark)); break;
                case "arc": t = Make(name, null, typeof(DxR.MarkArc)); break;
                default:
                    throw new System.Exception("Cannot load mark '" + markName + "'. Supported marks: " + string.Join(", ", Supported));
            }
            Templates[name] = t;
            return t;
        }

        static GameObject Make(string name, Mesh mesh, System.Type markType)
        {
            var go = new GameObject(name);
            go.transform.SetParent(_root, false);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = Mats.Opaque(Color.white, 0.55f);
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            var m = (DxR.Mark)go.AddComponent(markType);
            m.markName = name;
            return go;
        }
    }
}
