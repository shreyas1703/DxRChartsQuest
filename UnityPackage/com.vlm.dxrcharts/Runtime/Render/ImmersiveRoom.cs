using System.Collections.Generic;
using UnityEngine;

namespace VLMCharts
{
    public enum Backdrop { Dark, GridRoom, Light }

    /// <summary>
    /// Procedural "digital room": a large box around the viewer with deep-blue walls, a staggered
    /// brick-pattern grid of glowing light-blue lines, and a depth gradient (darker toward the far wall).
    /// Built entirely in code (one mesh for walls, one for lines); no textures or assets needed.
    /// </summary>
    public class ImmersiveRoom : MonoBehaviour
    {
        public float Width = 9f, Height = 4.5f, Depth = 14f;   // metres; the viewer stands near the back third
        public float FrontOffset = 4f;                         // how far the room extends behind the viewer
        public float RowHeight = 0.32f;                        // brick row height
        public float LineWidth = 0.014f;
        public Color WallNear = new Color(0.09f, 0.22f, 0.48f), WallFar = new Color(0.03f, 0.07f, 0.18f);
        public Color LineNear = new Color(0.45f, 0.75f, 1.0f), LineFar = new Color(0.10f, 0.25f, 0.55f);
        public int Seed = 11;

        static Material _mat;

        public static ImmersiveRoom Create(Transform parent)
        {
            var go = new GameObject("Immersive Grid Room");
            go.transform.SetParent(parent, false);
            var r = go.AddComponent<ImmersiveRoom>();
            r.Build();
            return r;
        }

        static Material Mat()
        {
            if (_mat == null)
            {
                var sh = Resources.Load<Shader>("DxRChartsVertexColor");
                _mat = new Material(sh != null ? sh : Shader.Find("Hidden/InternalErrorShader")) { name = "DXC Room" };
            }
            return _mat;
        }

        public void Build()
        {
            for (int i = transform.childCount - 1; i >= 0; i--) Destroy(transform.GetChild(i).gameObject);
            var rnd = new System.Random(Seed);
            float x0 = -Width / 2, x1 = Width / 2, y0 = 0f, y1 = Height, zNear = -FrontOffset, zFar = Depth - FrontOffset;

            var wv = new List<Vector3>(); var wc = new List<Color>(); var wt = new List<int>();
            var lv = new List<Vector3>(); var lc = new List<Color>(); var lt = new List<int>();

            // Each wall: origin, u axis (along), v axis (up/across), lengths, inward normal
            Wall(new Vector3(x0, y0, zNear), Vector3.forward, Vector3.up, zFar - zNear, Height, Vector3.right, rnd, wv, wc, wt, lv, lc, lt);   // left
            Wall(new Vector3(x1, y0, zNear), Vector3.forward, Vector3.up, zFar - zNear, Height, Vector3.left, rnd, wv, wc, wt, lv, lc, lt);    // right
            Wall(new Vector3(x0, y0, zNear), Vector3.forward, Vector3.right, zFar - zNear, Width, Vector3.up, rnd, wv, wc, wt, lv, lc, lt);    // floor
            Wall(new Vector3(x0, y1, zNear), Vector3.forward, Vector3.right, zFar - zNear, Width, Vector3.down, rnd, wv, wc, wt, lv, lc, lt);  // ceiling
            Wall(new Vector3(x0, y0, zFar), Vector3.right, Vector3.up, Width, Height, Vector3.back, rnd, wv, wc, wt, lv, lc, lt);              // far wall
            Wall(new Vector3(x0, y0, zNear), Vector3.right, Vector3.up, Width, Height, Vector3.forward, rnd, wv, wc, wt, lv, lc, lt);          // wall behind you

            MakeMesh("Walls", wv, wc, wt);
            MakeMesh("Grid lines", lv, lc, lt);
        }

        void MakeMesh(string name, List<Vector3> v, List<Color> c, List<int> t)
        {
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            var m = new Mesh { name = "DXC " + name };
            if (v.Count > 65000) m.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
            m.SetVertices(v); m.SetColors(c); m.SetTriangles(t, 0); m.RecalculateBounds();
            go.AddComponent<MeshFilter>().sharedMesh = m;
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = Mat();
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            mr.receiveShadows = false;
        }

        // Brightness by depth: near the viewer (z small) bright, far wall dark — like a tunnel fading into the distance.
        float Depth01(Vector3 p) { return Mathf.Clamp((p.z + FrontOffset) / Depth, 0f, 1f); }
        Color WallCol(Vector3 p) { float k = Depth01(p); return Color.Lerp(WallNear, WallFar, Mathf.Pow(k, 0.7f)); }
        Color LineCol(Vector3 p) { float k = Depth01(p); return Color.Lerp(LineNear, LineFar, Mathf.Pow(k, 0.8f)); }

        void Wall(Vector3 o, Vector3 u, Vector3 v, float lenU, float lenV, Vector3 n, System.Random rnd,
                  List<Vector3> wv, List<Color> wc, List<int> wt, List<Vector3> lv, List<Color> lc, List<int> lt)
        {
            // tessellated wall so the depth gradient is smooth
            int su = Mathf.Max(1, Mathf.CeilToInt(lenU / 1f)), sv = Mathf.Max(1, Mathf.CeilToInt(lenV / 1f));
            int b = wv.Count;
            for (int j = 0; j <= sv; j++)
                for (int i = 0; i <= su; i++)
                {
                    Vector3 p = o + u * (lenU * i / su) + v * (lenV * j / sv);
                    wv.Add(p); wc.Add(WallCol(p));
                }
            for (int j = 0; j < sv; j++)
                for (int i = 0; i < su; i++)
                {
                    int k = b + j * (su + 1) + i;
                    wt.AddRange(new[] { k, k + su + 1, k + 1, k + 1, k + su + 1, k + su + 2 });
                }

            // brick grid lines, lifted 1 cm off the wall toward the viewer
            Vector3 lift = n * 0.01f;
            int rows = Mathf.Max(1, Mathf.RoundToInt(lenV / RowHeight));
            float rh = lenV / rows;
            for (int r = 0; r <= rows; r++)
                Seg(o + v * (r * rh) + lift, u, lenU, v, lv, lc, lt);                         // horizontal row lines
            for (int r = 0; r < rows; r++)
            {
                float pos = (float)rnd.NextDouble() * 0.6f;
                while (pos < lenU)
                {
                    Seg(o + u * pos + v * (r * rh) + lift, v, rh, u, lv, lc, lt);              // vertical brick joints
                    pos += 0.35f + (float)rnd.NextDouble() * 1.1f;
                }
            }
        }

        void Seg(Vector3 start, Vector3 dir, float len, Vector3 side, List<Vector3> v, List<Color> c, List<int> t)
        {
            // split long lines so the depth gradient applies along them
            int pieces = Mathf.Max(1, Mathf.CeilToInt(len / 1.5f));
            Vector3 w = side * (LineWidth * 0.5f);
            for (int i = 0; i < pieces; i++)
            {
                Vector3 a = start + dir * (len * i / pieces), bb = start + dir * (len * (i + 1) / pieces);
                int k = v.Count;
                v.Add(a - w); v.Add(a + w); v.Add(bb + w); v.Add(bb - w);
                c.Add(LineCol(a)); c.Add(LineCol(a)); c.Add(LineCol(bb)); c.Add(LineCol(bb));
                t.AddRange(new[] { k, k + 1, k + 2, k, k + 2, k + 3 });
            }
        }
    }
}
