using System;
using System.Collections.Generic;
using System.Globalization;
using DxRSimpleJSON;
using UnityEngine;
using VLMCharts;

namespace DxR
{
    /// <summary>
    /// DxR axis, rebuilt procedurally (the original used HoloToolkit prefabs). Honours the DxR axis specs
    /// produced by Mark.Infer: title, length, orient/face (x: bottom/front, y: left/front, z: bottom/left),
    /// ticks, labels, values, color, grid. Labels are billboarded and sit on dark plates so they stay
    /// legible in the headset and in the Quest's video recording.
    /// Extra optional spec keys: "labelAngle" (degrees, e.g. -45 for long category names), "format"
    /// (C# numeric format for tick labels, e.g. "0.0").
    /// </summary>
    public class Axis : MonoBehaviour
    {
        public static float TickLabelHeight = 0.032f;   // m
        public static float TitleHeight = 0.036f;      // m
        static readonly float S = Vis.SIZE_UNIT_SCALE_FACTOR;

        public List<string> TickLabels = new List<string>();

        public void Build(JSONNode axisSpecs, Scale scale, Vector3 visSizeMm)
        {
            string orient = axisSpecs["orient"].Value, face = axisSpecs["face"].Value;
            float length = (axisSpecs["length"] != null ? axisSpecs["length"].AsFloat : 0f) * S;
            Vector3 size = visSizeMm * S;

            // Direction of the axis and where labels go (DxR conventions).
            Vector3 dir, labelDir;
            if (orient == "left") { dir = Vector3.up; labelDir = Vector3.left; }                    // y on the front-left edge
            else if (face == "left" || face == "right") { dir = Vector3.forward; labelDir = (face == "right" ? Vector3.right : Vector3.left) + Vector3.down * 0.4f; }  // z along a bottom side edge
            else { dir = Vector3.right; labelDir = Vector3.down; }                                    // x on the bottom-front edge

            Color axisColor = Color.white;
            if (axisSpecs["color"] != null) ColorUtility.TryParseHtmlString(axisSpecs["color"].Value, out axisColor);
            var lineMat = Mats.Opaque(axisColor);
            // DxR places z on the left face; "face":"right" (port extension) moves it to x = width to keep the origin uncluttered.
            if (dir == Vector3.forward && face == "right") transform.localPosition = new Vector3(size.x, 0f, 0f);
            Prims.Line("AxisLine", transform, Vector3.zero, dir * length, 0.004f, lineMat);

            bool grid = axisSpecs["grid"] != null && axisSpecs["grid"].AsBool;
            bool labels = axisSpecs["labels"] == null || axisSpecs["labels"].AsBool;
            bool ticks = axisSpecs["ticks"] == null || axisSpecs["ticks"].AsBool;
            float labelAngle = axisSpecs["labelAngle"] != null ? axisSpecs["labelAngle"].AsFloat : 0f;
            string format = axisSpecs["format"] != null ? axisSpecs["format"].Value : null;
            var gridMat = Mats.Opaque(new Color(0.32f, 0.35f, 0.42f));

            if (ticks && axisSpecs["values"] != null && scale != null)
            {
                for (int i = 0; i < axisSpecs["values"].Count; i++)
                {
                    string domainValue = axisSpecs["values"][i].Value;
                    float pos = float.Parse(scale.ApplyScale(domainValue), CultureInfo.InvariantCulture) * S;
                    Vector3 p = dir * pos;
                    Prims.Line("Tick", transform, p, p + labelDir.normalized * 0.012f, 0.003f, lineMat);
                    if (grid) DrawGrid(dir, p, size, gridMat);
                    if (!labels) continue;
                    string text = FormatTick(domainValue, format);
                    TickLabels.Add(text);
                    var align = TextLabel.HAlign.Center;
                    Vector3 lp = p + labelDir.normalized * 0.035f;
                    if (dir == Vector3.up) { align = TextLabel.HAlign.Right; lp = p + Vector3.left * 0.022f; }
                    if (dir == Vector3.forward) { align = face == "right" ? TextLabel.HAlign.Left : TextLabel.HAlign.Right; lp = p + labelDir.normalized * 0.042f; }
                    if (labelAngle != 0f) { align = TextLabel.HAlign.Right; lp = p + Vector3.down * 0.02f; }
                    var l = TextLabel.Create("TickLabel " + text, transform, lp, text, TickLabelHeight, Color.white, align, true, true);
                    l.roll = labelAngle;
                }
            }

            if (axisSpecs["title"] != null && axisSpecs["title"].Value.Length > 0)
            {
                Vector3 tp;
                if (dir == Vector3.up) tp = dir * length + Vector3.up * 0.06f;                       // above the y axis
                else if (dir == Vector3.forward) tp = dir * (length * 0.5f) + new Vector3(face == "right" ? 0.24f : -0.24f, -0.11f, 0f);
                else tp = dir * (length * 0.5f) + Vector3.down * (labelAngle != 0f ? 0.2f : 0.1f);
                var t = TextLabel.Create("AxisTitle", transform, tp, axisSpecs["title"].Value, TitleHeight, new Color(1f, 0.9f, 0.45f),
                    TextLabel.HAlign.Center, true, true);
                t.bold = true;
            }
        }

        void DrawGrid(Vector3 dir, Vector3 p, Vector3 size, Material m)
        {
            float t = 0.0012f;
            float W = size.x, H = size.y, D = size.z;
            if (dir == Vector3.up)            // horizontal lines: back wall + left wall
            {
                Prims.Line("Grid", transform, new Vector3(0, p.y, D), new Vector3(W, p.y, D), t, m);
                if (D > 0.02f) Prims.Line("Grid", transform, new Vector3(0, p.y, 0), new Vector3(0, p.y, D), t, m);
            }
            else if (dir == Vector3.right)    // vertical lines on the back wall + lines across the floor
            {
                Prims.Line("Grid", transform, new Vector3(p.x, 0, D), new Vector3(p.x, H, D), t, m);
                if (D > 0.02f) Prims.Line("Grid", transform, new Vector3(p.x, 0, 0), new Vector3(p.x, 0, D), t, m);
            }
            else                              // z: across the floor + up the left wall (in vis coordinates)
            {
                Vector3 o = -transform.localPosition;   // axis may be shifted to x = width
                Prims.Line("Grid", transform, o + new Vector3(0, 0, p.z), o + new Vector3(W, 0, p.z), t, m);
                Prims.Line("Grid", transform, o + new Vector3(0, 0, p.z), o + new Vector3(0, H, p.z), t, m);
            }
        }

        string FormatTick(string domainValue, string format)
        {
            double v;
            if (format != null && double.TryParse(domainValue, NumberStyles.Float, CultureInfo.InvariantCulture, out v))
                return v.ToString(format, CultureInfo.InvariantCulture);
            return domainValue;
        }
    }
}
