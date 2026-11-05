using System.Collections.Generic;
using DxRSimpleJSON;
using UnityEngine;
using VLMCharts;

namespace DxR
{
    /// <summary>
    /// DxR color legend, rebuilt procedurally (the original used HoloToolkit ObjectCollection prefabs).
    /// Uses the legend specs inferred by Mark.Infer: title, type (symbol / gradient), x, y, z (mm).
    /// </summary>
    public class Legend : MonoBehaviour
    {
        public static float EntryHeight = 0.03f;   // m
        public List<string> Entries = new List<string>();

        public void Build(JSONNode legendSpecs, ChannelEncoding ce, string markName)
        {
            float s = Vis.SIZE_UNIT_SCALE_FACTOR;
            float x = legendSpecs["x"] != null ? legendSpecs["x"].AsFloat * s : 0.5f;
            float y = legendSpecs["y"] != null ? legendSpecs["y"].AsFloat * s : 0.5f;
            float z = legendSpecs["z"] != null ? legendSpecs["z"].AsFloat * s : 0f;
            transform.localPosition = new Vector3(x + 0.06f, y, z);

            string title = legendSpecs["title"] != null ? legendSpecs["title"].Value : ce.field;
            var t = TextLabel.Create("LegendTitle", transform, Vector3.zero, title, EntryHeight * 1.1f, new Color(1f, 0.9f, 0.45f),
                TextLabel.HAlign.Left, true, true);
            t.bold = true;

            if (ce.scale == null) return;
            float step = EntryHeight * 1.6f;
            bool sphere = markName == "sphere" || markName == "point" || markName == "line";
            if (legendSpecs["type"] != null && legendSpecs["type"].Value == "gradient" && ce.scale.domain.Count >= 2)
            {
                BuildGradient(ce.scale);
                return;
            }
            for (int i = 0; i < ce.scale.domain.Count; i++)
                AddEntry(i + 1, step, ce.scale.ApplyScale(ce.scale.domain[i]), ce.scale.domain[i], sphere);
        }

        /// <summary>
        /// Continuous colour bar (port extension): highest value on top, a tick + label at every domain stop of the
        /// sequential scale, so a value can be read back from a cell's colour.
        /// </summary>
        void BuildGradient(Scale scale)
        {
            float lo = float.Parse(scale.domain[0], System.Globalization.CultureInfo.InvariantCulture);
            float hi = float.Parse(scale.domain[scale.domain.Count - 1], System.Globalization.CultureInfo.InvariantCulture);
            float top = -EntryHeight * 1.4f, barH = GradientHeight, barW = EntryHeight * 1.1f;
            const int segments = 60;
            for (int i = 0; i < segments; i++)
            {
                float v = hi - (hi - lo) * (i + 0.5f) / segments;
                Color c;
                if (!ColorUtility.TryParseHtmlString(scale.ApplyScale(v.ToString(System.Globalization.CultureInfo.InvariantCulture)), out c)) c = Color.white;
                var seg = Prims.MeshObject("GradientCell", transform, Prims.CubeMesh, Mats.Opaque(c));
                seg.transform.localPosition = new Vector3(barW * 0.5f, top - barH * (i + 0.5f) / segments, 0f);
                seg.transform.localScale = new Vector3(barW, barH / segments * 1.02f, 0.004f);
            }
            var tickMat = Mats.Opaque(Color.white);
            foreach (string d in scale.domain)
            {
                float v = float.Parse(d, System.Globalization.CultureInfo.InvariantCulture);
                float y = top - barH * (hi - v) / (hi - lo);
                Prims.Line("Tick", transform, new Vector3(barW, y, 0f), new Vector3(barW + 0.012f, y, 0f), 0.003f, tickMat);
                TextLabel.Create("LegendLabel " + d, transform, new Vector3(barW + 0.02f, y, 0f), d, EntryHeight, Color.white,
                    TextLabel.HAlign.Left, true, true);
                Entries.Add(d);
            }
        }

        public static float GradientHeight = 0.36f;   // m

        void AddEntry(int row, float step, string colorHex, string text, bool sphere)
        {
            Color c;
            if (!ColorUtility.TryParseHtmlString(colorHex, out c)) c = Color.white;
            float yy = -row * step;
            var sw = Prims.MeshObject("Swatch " + text, transform, sphere ? Prims.SphereMesh : Prims.CubeMesh, Mats.Opaque(c, 0.3f));
            sw.transform.localPosition = new Vector3(0.012f, yy, 0f);
            sw.transform.localScale = Vector3.one * EntryHeight * 0.85f;
            TextLabel.Create("LegendLabel " + text, transform, new Vector3(0.032f, yy, 0f), text, EntryHeight, Color.white,
                TextLabel.HAlign.Left, true, true);
            Entries.Add(text);
        }
    }
}
