using System.Collections.Generic;
using System.Globalization;
using UnityEngine;

namespace DxR
{
    /// <summary>
    /// New DxR mark for pie / donut charts (DxR has no arc mark). One instance per slice: a 3D extruded
    /// circular sector standing upright, facing the viewer (-Z), centred on the mark's x/y/z position.
    ///
    /// Channels (in addition to the DxR base channels x, y, z, color, …):
    ///   startangle, endangle  degrees, 0 = 12 o'clock, clockwise (precomputed per slice; use scale type "none")
    ///   radius                outer radius in mm (default 200)
    ///   innerradius           inner radius in mm (0 = pie, &gt;0 = donut)
    ///   thickness             extrusion depth in mm (default 40)
    ///   explode               radial offset of the slice in mm (default 0)
    ///   label                 text placed just outside the slice (e.g. category, or "Action 19.9%")
    /// </summary>
    public class MarkArc : Mark
    {
        float startDeg = 0f, endDeg = 90f, radiusMm = 200f, innerMm = 0f, thicknessMm = 40f, explodeMm = 0f;
        Mesh mesh;

        public override List<string> GetChannelsList()
        {
            var l = new List<string> { "startangle", "endangle", "radius", "innerradius", "thickness", "explode" };
            l.AddRange(base.GetChannelsList());
            return l;
        }

        public override void SetChannelValue(string channel, string value)
        {
            switch (channel)
            {
                case "startangle": startDeg = F(value); Rebuild(); break;
                case "endangle": endDeg = F(value); Rebuild(); break;
                case "radius": radiusMm = F(value); Rebuild(); break;
                case "innerradius": innerMm = F(value); Rebuild(); break;
                case "thickness": thicknessMm = F(value); Rebuild(); break;
                case "explode": explodeMm = F(value); Rebuild(); break;
                default: base.SetChannelValue(channel, value); break;
            }
        }

        static float F(string v) { return float.Parse(v, CultureInfo.InvariantCulture); }

        Vector3 Dir(float deg)
        {
            float a = deg * Mathf.Deg2Rad;          // 0° = up, clockwise as seen by the viewer (looking along +Z)
            return new Vector3(Mathf.Sin(a), Mathf.Cos(a), 0f);
        }

        void Rebuild()
        {
            float s = Vis.SIZE_UNIT_SCALE_FACTOR;
            float r1 = radiusMm * s, r0 = Mathf.Max(0f, innerMm) * s, th = Mathf.Max(0.001f, thicknessMm * s);
            float a0 = startDeg, a1 = endDeg;
            if (a1 < a0) { float t = a0; a0 = a1; a1 = t; }
            int segs = Mathf.Max(2, Mathf.CeilToInt((a1 - a0) / 3f));
            Vector3 off = Dir((a0 + a1) * 0.5f) * (explodeMm * s);

            var v = new List<Vector3>(); var tri = new List<int>();
            // front (z = 0) and back (z = th) faces
            for (int face = 0; face < 2; face++)
            {
                float z = face == 0 ? 0f : th;
                for (int i = 0; i < segs; i++)
                {
                    float b0 = Mathf.Lerp(a0, a1, i / (float)segs), b1 = Mathf.Lerp(a0, a1, (i + 1) / (float)segs);
                    Vector3 o0 = Dir(b0) * r1, o1 = Dir(b1) * r1, i0 = Dir(b0) * r0, i1 = Dir(b1) * r0;
                    Quad(v, tri, i0, o0, o1, i1, z, off);
                }
            }
            // outer and inner rims
            for (int i = 0; i < segs; i++)
            {
                float b0 = Mathf.Lerp(a0, a1, i / (float)segs), b1 = Mathf.Lerp(a0, a1, (i + 1) / (float)segs);
                Side(v, tri, Dir(b0) * r1, Dir(b1) * r1, th, off);
                if (r0 > 0f) Side(v, tri, Dir(b1) * r0, Dir(b0) * r0, th, off);
            }
            // the two radial cut faces
            Side(v, tri, Dir(a0) * r0, Dir(a0) * r1, th, off);
            Side(v, tri, Dir(a1) * r1, Dir(a1) * r0, th, off);

            // Orient every triangle away from the slice centroid so Unity (clockwise = front) renders it.
            Vector3 c = Dir((a0 + a1) * 0.5f) * ((r0 + r1) * 0.5f) + off + new Vector3(0, 0, th * 0.5f);
            for (int i = 0; i < tri.Count; i += 3)
            {
                Vector3 p0 = v[tri[i]], p1 = v[tri[i + 1]], p2 = v[tri[i + 2]];
                Vector3 n = Vector3.Cross(p1 - p0, p2 - p0);
                if (Vector3.Dot(n, (p0 + p1 + p2) / 3f - c) < 0f) { int t = tri[i + 1]; tri[i + 1] = tri[i + 2]; tri[i + 2] = t; }
            }

            if (mesh == null) { mesh = new Mesh { name = "DxR arc" }; }
            mesh.Clear();
            mesh.SetVertices(v); mesh.SetTriangles(tri, 0); mesh.RecalculateNormals(); mesh.RecalculateBounds();
            var mf = GetComponent<MeshFilter>();
            if (mf != null) mf.sharedMesh = mesh;
            PlaceLabel();
        }

        static void Quad(List<Vector3> v, List<int> tri, Vector3 a, Vector3 b, Vector3 c, Vector3 d, float z, Vector3 off)
        {
            int k = v.Count;
            v.Add(a + off + Vector3.forward * z); v.Add(b + off + Vector3.forward * z); v.Add(c + off + Vector3.forward * z); v.Add(d + off + Vector3.forward * z);
            tri.AddRange(new[] { k, k + 1, k + 2, k, k + 2, k + 3 });
        }

        static void Side(List<Vector3> v, List<int> tri, Vector3 a, Vector3 b, float th, Vector3 off)
        {
            int k = v.Count;
            v.Add(a + off); v.Add(b + off); v.Add(b + off + Vector3.forward * th); v.Add(a + off + Vector3.forward * th);
            tri.AddRange(new[] { k, k + 1, k + 2, k, k + 2, k + 3 });
        }

        protected override void SetLabel(string value)
        {
            labelText = value;
            if (labelObject == null)
                labelObject = VLMCharts.TextLabel.Create("label", transform, Vector3.zero, value, LabelHeight * 1.1f, Color.white,
                    VLMCharts.TextLabel.HAlign.Center, true, true);
            labelObject.Set(value);
            PlaceLabel();
        }

        void PlaceLabel()
        {
            if (labelObject == null) return;
            float s = Vis.SIZE_UNIT_SCALE_FACTOR;
            float mid = (startDeg + endDeg) * 0.5f;
            Vector3 d = Dir(mid);
            float r = (radiusMm + explodeMm) * s + 0.05f + 0.025f * Mathf.Abs(d.x);   // wider labels need more room at the sides
            labelObject.transform.localPosition = d * r + new Vector3(0, 0, -0.01f);
            labelObject.align = d.x > 0.35f ? VLMCharts.TextLabel.HAlign.Left : d.x < -0.35f ? VLMCharts.TextLabel.HAlign.Right : VLMCharts.TextLabel.HAlign.Center;
        }

        protected override void LateUpdate() { }   // label is a child placed in PlaceLabel()
    }
}
