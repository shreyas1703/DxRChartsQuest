using System.Collections.Generic;
using UnityEngine;

namespace VLMCharts
{
    /// <summary>
    /// World-space text built directly from the built-in dynamic font's glyph atlas.
    /// Exact bounds are known, so every label can have a dark backing plate — the single biggest
    /// win for readability in the Quest's compressed screen recordings.
    /// </summary>
    public class TextLabel : MonoBehaviour
    {
        public enum HAlign { Left, Center, Right }

        public const int AtlasPx = 48;                 // glyph raster size in the font atlas
        public static float GlobalScale = 1f;          // readability multiplier (Label size button)
        static Font _font;
        static readonly List<TextLabel> All = new List<TextLabel>();
        static bool _hooked;

        [TextArea] public string text = "";
        public float height = 0.03f;                   // world height of one line (meters, before GlobalScale)
        public Color color = Color.white;
        public HAlign align = HAlign.Center;
        public bool plate = true;
        public Color plateColor = Mats.PlateBg;
        public float padding = 0.25f;                  // in line heights
        public bool billboard = true;
        public float roll = 0f;                        // degrees, applied after billboarding (slanted axis labels)
        public bool bold = true;
        public bool ignoreGlobalScale = false;

        Mesh _mesh;
        MeshRenderer _mr;
        Transform _plate;
        string _builtText; float _builtScale = -1f; float _builtHeight; HAlign _builtAlign; Color _builtColor, _builtPlateColor; bool _builtBold, _builtPlate; bool _dirty = true;

        public Vector2 Size { get; private set; }      // world size incl. padding (before transform scale)

        public static Font Font
        {
            get
            {
                if (_font == null)
                {
                    try { _font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"); } catch { }
                    if (_font == null) { try { _font = Resources.GetBuiltinResource<Font>("Arial.ttf"); } catch { } }
                }
                if (!_hooked) { Font.textureRebuilt += OnFontRebuilt; _hooked = true; }
                return _font;
            }
        }

        static void OnFontRebuilt(Font f)
        {
            if (f != _font) return;
            for (int i = 0; i < All.Count; i++) if (All[i] != null) All[i]._dirty = true;
        }

        public static void RebuildAll() { foreach (var l in All) if (l != null) l._dirty = true; }

        public static TextLabel Create(string name, Transform parent, Vector3 localPos, string text, float height,
                                       Color color, HAlign align = HAlign.Center, bool plate = true, bool billboard = true)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            var l = go.AddComponent<TextLabel>();
            l.text = text; l.height = height; l.color = color; l.align = align; l.plate = plate; l.billboard = billboard;
            l.Rebuild();
            return l;
        }

        public void Set(string t) { if (t != text) { text = t; _dirty = true; } }
        public void SetColor(Color c) { if (c != color) { color = c; _dirty = true; } }

        void OnEnable() { if (!All.Contains(this)) All.Add(this); _dirty = true; }
        void OnDisable() { All.Remove(this); }
        void OnDestroy() { if (_mesh != null) { if (Application.isPlaying) Destroy(_mesh); else DestroyImmediate(_mesh); } }

        void LateUpdate()
        {
            float s = ignoreGlobalScale ? 1f : GlobalScale;
            if (_dirty || text != _builtText || s != _builtScale || height != _builtHeight || align != _builtAlign || color != _builtColor
                || bold != _builtBold || plate != _builtPlate || plateColor != _builtPlateColor) Rebuild();
            if (billboard && Application.isPlaying)
            {
                var cam = Camera.main;
                if (cam != null)
                {
                    Vector3 fwd = transform.position - cam.transform.position;
                    if (fwd.sqrMagnitude > 1e-6f) transform.rotation = Quaternion.LookRotation(fwd, cam.transform.up) * Quaternion.Euler(0f, 0f, roll);
                }
            }
        }

        public void Rebuild()
        {
            _dirty = false;
            var font = Font;
            if (font == null) return;
            if (_mesh == null)
            {
                _mesh = new Mesh { name = "S3D Text" };
                _mesh.MarkDynamic();
                var mf = GetComponent<MeshFilter>(); if (mf == null) mf = gameObject.AddComponent<MeshFilter>();
                mf.sharedMesh = _mesh;
                _mr = GetComponent<MeshRenderer>(); if (_mr == null) _mr = gameObject.AddComponent<MeshRenderer>();
                _mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                _mr.receiveShadows = false;
            }
            FontStyle style = bold ? FontStyle.Bold : FontStyle.Normal;
            string t = text ?? "";
            font.RequestCharactersInTexture(t, AtlasPx, style);
            _mr.sharedMaterial = Mats.Text(font.material.mainTexture);

            float s = ignoreGlobalScale ? 1f : GlobalScale;
            float lineH = height * s;
            float k = lineH / (AtlasPx * 1.25f);          // world units per atlas pixel
            float ascent = AtlasPx * 0.92f * k;

            var verts = new List<Vector3>(); var uvs = new List<Vector2>(); var cols = new List<Color>(); var tris = new List<int>();
            string[] lines = t.Split('\n');
            float maxW = 0f;
            var widths = new float[lines.Length];
            for (int li = 0; li < lines.Length; li++)
            {
                float w = 0f; CharacterInfo ci;
                foreach (char c in lines[li]) if (font.GetCharacterInfo(c, out ci, AtlasPx, style)) w += ci.advance * k;
                widths[li] = w; maxW = Mathf.Max(maxW, w);
            }
            float totalH = lines.Length * lineH;
            float top = totalH * 0.5f;
            for (int li = 0; li < lines.Length; li++)
            {
                float x = align == HAlign.Left ? 0f : align == HAlign.Center ? -widths[li] * 0.5f : -widths[li];
                float baseline = top - li * lineH - ascent * 0.95f;
                CharacterInfo ci;
                foreach (char c in lines[li])
                {
                    if (!font.GetCharacterInfo(c, out ci, AtlasPx, style)) continue;
                    int b = verts.Count;
                    verts.Add(new Vector3(x + ci.minX * k, baseline + ci.minY * k, 0));
                    verts.Add(new Vector3(x + ci.maxX * k, baseline + ci.minY * k, 0));
                    verts.Add(new Vector3(x + ci.maxX * k, baseline + ci.maxY * k, 0));
                    verts.Add(new Vector3(x + ci.minX * k, baseline + ci.maxY * k, 0));
                    uvs.Add(ci.uvBottomLeft); uvs.Add(ci.uvBottomRight); uvs.Add(ci.uvTopRight); uvs.Add(ci.uvTopLeft);
                    for (int q = 0; q < 4; q++) cols.Add(color);
                    tris.Add(b); tris.Add(b + 2); tris.Add(b + 1); tris.Add(b); tris.Add(b + 3); tris.Add(b + 2);
                    x += ci.advance * k;
                }
            }
            _mesh.Clear();
            _mesh.SetVertices(verts); _mesh.SetUVs(0, uvs); _mesh.SetColors(cols); _mesh.SetTriangles(tris, 0);
            _mesh.RecalculateBounds();

            float pad = lineH * padding;
            float left = align == HAlign.Left ? 0f : align == HAlign.Center ? -maxW * 0.5f : -maxW;
            Size = new Vector2(maxW + 2 * pad, totalH + 2 * pad * 0.6f);
            if (plate && t.Length > 0)
            {
                if (_plate == null)
                {
                    var existing = transform.Find("plate");
                    _plate = existing != null ? existing : Prims.MeshObject("plate", transform, Prims.QuadMesh, Mats.Transparent(plateColor)).transform;
                }
                _plate.gameObject.SetActive(true);
                _plate.GetComponent<MeshRenderer>().sharedMaterial = Mats.Transparent(plateColor);
                _plate.localPosition = new Vector3(left + maxW * 0.5f, 0f, lineH * 0.02f);
                _plate.localRotation = Quaternion.identity;
                _plate.localScale = new Vector3(Size.x, Size.y, 1f);
            }
            else if (_plate != null) _plate.gameObject.SetActive(false);

            _builtText = t; _builtScale = s; _builtHeight = height; _builtAlign = align; _builtColor = color;
            _builtBold = bold; _builtPlate = plate; _builtPlateColor = plateColor;
        }
    }
}
