using System.Collections.Generic;
using UnityEngine;
using DxRSimpleJSON;
using System;

namespace DxR
{
    /// <summary>
    /// DxR visualization component — Quest/OpenXR port of DxR's Vis (github.com/ronellsicat/DxR, MIT).
    ///
    /// Same grammar and pipeline as the original: parse JSON specs → load data (CSV/JSON) →
    /// infer missing specs (scales, axes, legends) with Mark.Infer → one mark instance per datum →
    /// apply channel encodings through scales → axes → legends.
    ///
    /// Removed for the port (they depend on HoloToolkit / HoloLens): in-situ GUI editor, gaze tooltips,
    /// interaction filters, writing specs back to disk. Marks, axes and legends are built procedurally
    /// (MarkFactory, Axis, Legend) instead of from HoloToolkit prefabs. Added: the spec "title" is drawn.
    /// Coordinates are DxR's: specs in millimetres, origin at the bottom-left-front corner.
    /// </summary>
    public class Vis : MonoBehaviour
    {
        public string visSpecsURL = "example.json";
        public bool autoLoadOnAwake = false;
        public bool verbose = false;

        public static string UNDEFINED = "undefined";
        public static float SIZE_UNIT_SCALE_FACTOR = 1.0f / 1000.0f;   // mm → m
        public static float DEFAULT_VIS_DIMS = 500.0f;

        JSONNode visSpecs;
        JSONNode visSpecsInferred;
        Parser parser = null;

        string title;
        float width, height, depth;
        public Data data;
        public List<GameObject> markInstances;

        GameObject viewParentObject, marksParentObject, guidesParentObject;
        GameObject markPrefab;
        List<ChannelEncoding> channelEncodings;

        public JSONNode InferredSpecs { get { return visSpecsInferred; } }
        public string Title { get { return title; } }
        public bool IsReady { get; private set; }

        void Awake()
        {
            EnsureHierarchy();
            if (autoLoadOnAwake) Load(visSpecsURL);
        }

        void EnsureHierarchy()
        {
            if (viewParentObject != null) return;
            Transform v = transform.Find("DxRView");
            viewParentObject = v != null ? v.gameObject : new GameObject("DxRView");
            viewParentObject.transform.SetParent(transform, false);
            marksParentObject = Child(viewParentObject, "DxRMarks");
            guidesParentObject = Child(viewParentObject, "DxRGuides");
        }

        static GameObject Child(GameObject parent, string name)
        {
            Transform t = parent.transform.Find(name);
            if (t != null) return t.gameObject;
            var go = new GameObject(name);
            go.transform.SetParent(parent.transform, false);
            return go;
        }

        /// <summary>Load (or reload) a spec file from StreamingAssets/DxRSpecs/.</summary>
        public void Load(string specsUrl)
        {
            EnsureHierarchy();
            IsReady = false;
            visSpecsURL = specsUrl;
            if (parser == null) parser = new Parser();
            parser.Parse(visSpecsURL, out visSpecs);
            UpdateVis();
            IsReady = true;
        }

        public Vector3 GetVisSize() { return new Vector3(width, height, depth); }
        public int GetNumMarkInstances() { return markInstances == null ? 0 : markInstances.Count; }

        // ------------------------------------------------------------------ pipeline (as in DxR)
        void UpdateVis()
        {
            DeleteAll();
            UpdateVisConfig();
            UpdateVisData();
            UpdateMarkPrefab();
            InferVisSpecs();
            ConstructVis(visSpecsInferred);
        }

        void ConstructVis(JSONNode specs)
        {
            channelEncodings = CreateChannelEncodingObjects(specs, data);
            ConstructMarkInstances();
            ApplyChannelEncodings();
            if (visSpecs["mark"].Value == "line") ConnectLines(specs);
            ConstructAxes(specs);
            ConstructLegends(specs);
            ConstructTitle();
        }

        void DeleteAll()
        {
            for (int i = guidesParentObject.transform.childCount - 1; i >= 0; i--) Destroy(guidesParentObject.transform.GetChild(i).gameObject);
            for (int i = marksParentObject.transform.childCount - 1; i >= 0; i--) Destroy(marksParentObject.transform.GetChild(i).gameObject);
        }

        void UpdateVisConfig()
        {
            title = visSpecs["title"] != null ? visSpecs["title"].Value : "";
            width = GetDim("width"); height = GetDim("height"); depth = GetDim("depth");
        }

        float GetDim(string key)
        {
            if (visSpecs[key] == null) visSpecs.Add(key, new JSONNumber(DEFAULT_VIS_DIMS));
            return visSpecs[key].AsFloat;
        }

        void UpdateVisData()
        {
            if (visSpecs["data"]["url"] != "inline")
                visSpecs["data"].Add("values", parser.CreateValuesSpecs(visSpecs["data"]["url"]));
            data = BuildData(visSpecs["data"]["values"]);
            if (verbose) Debug.Log("[DxR] " + data.values.Count + " data rows, fields: " + string.Join(", ", data.fieldNames.ToArray()));
        }

        /// <summary>Same row handling as DxR: rows with a null field are skipped.</summary>
        public static Data BuildData(JSONNode valuesSpecs)
        {
            var d = new Data { fieldNames = new List<string>(), values = new List<Dictionary<string, string>>() };
            foreach (KeyValuePair<string, JSONNode> kvp in valuesSpecs[0].AsObject) d.fieldNames.Add(kvp.Key);
            foreach (JSONNode value in valuesSpecs.Children)
            {
                var row = new Dictionary<string, string>();
                bool hasNull = false;
                foreach (string f in d.fieldNames)
                {
                    if (value[f].IsNull) { hasNull = true; break; }
                    row.Add(f, value[f]);
                }
                if (!hasNull) d.values.Add(row);
            }
            return d;
        }

        void UpdateMarkPrefab()
        {
            markPrefab = VLMCharts.MarkFactory.GetTemplate(visSpecs["mark"].Value);
        }

        void InferVisSpecs()
        {
            markPrefab.GetComponent<Mark>().Infer(data, visSpecs, out visSpecsInferred, visSpecsURL);
        }

        // ------------------------------------------------------------------ channel encodings (as in DxR, made static for testing)
        public static List<ChannelEncoding> CreateChannelEncodingObjects(JSONNode specs, Data data)
        {
            var list = new List<ChannelEncoding>();
            foreach (KeyValuePair<string, JSONNode> kvp in specs["encoding"].AsObject)
            {
                var ce = new ChannelEncoding();
                ce.channel = kvp.Key;
                JSONNode channelSpecs = kvp.Value;
                if (channelSpecs["value"] != null)
                {
                    ce.value = channelSpecs["value"].Value.ToString();
                    if (channelSpecs["type"] != null) ce.valueDataType = channelSpecs["type"].Value.ToString();
                }
                else
                {
                    ce.field = channelSpecs["field"];
                    if (!data.fieldNames.Contains(ce.field))
                        throw new Exception("Cannot find data field " + ce.field + " in data. Please check your spelling (case sensitive).");
                    if (channelSpecs["type"] == null) throw new Exception("Missing type for field in channel " + ce.channel);
                    ce.fieldDataType = channelSpecs["type"];
                }
                JSONNode scaleSpecs = channelSpecs["scale"];
                if (scaleSpecs != null) ce.scale = CreateScale(scaleSpecs);
                list.Add(ce);
            }
            return list;
        }

        public static Scale CreateScale(JSONNode scaleSpecs)
        {
            switch (scaleSpecs["type"].Value.ToString())
            {
                case "none": return new ScaleNone(scaleSpecs);
                case "linear": return new ScaleLinear(scaleSpecs);
                case "band": return new ScaleBand(scaleSpecs);
                case "point": return new ScalePoint(scaleSpecs);
                case "ordinal": return new ScaleOrdinal(scaleSpecs);
                case "sequential": return new ScaleSequential(scaleSpecs);
                default: return null;
            }
        }

        /// <summary>The value DxR sends to SetChannelValue for one datum.</summary>
        public static string ChannelValueFor(ChannelEncoding ce, Dictionary<string, string> datum)
        {
            if (ce.value != UNDEFINED) return ce.value;
            if (ce.scale == null) throw new Exception("No scale for channel " + ce.channel);
            return ce.scale.ApplyScale(datum[ce.field]);
        }

        void ConstructMarkInstances()
        {
            markInstances = new List<GameObject>();
            foreach (Dictionary<string, string> dataValue in data.values)
            {
                GameObject markInstance = Instantiate(markPrefab, marksParentObject.transform);
                markInstance.name = markPrefab.name;
                markInstance.transform.localPosition = Vector3.zero;
                markInstance.transform.localRotation = Quaternion.identity;
                markInstance.SetActive(true);
                markInstance.GetComponent<Mark>().datum = dataValue;
                markInstances.Add(markInstance);
            }
        }

        void ApplyChannelEncodings()
        {
            bool isDirectionChanged = false;
            foreach (ChannelEncoding ch in channelEncodings)
            {
                for (int i = 0; i < markInstances.Count; i++)
                {
                    Mark m = markInstances[i].GetComponent<Mark>();
                    m.SetChannelValue(ch.channel, ChannelValueFor(ch, m.datum));
                }
                if (ch.channel == "xdirection" || ch.channel == "ydirection" || ch.channel == "zdirection") isDirectionChanged = true;
            }
            if (isDirectionChanged)
                foreach (var mi in markInstances) mi.GetComponent<Mark>().SetRotation();
        }

        /// <summary>
        /// Line mark (port extension, Vega-Lite semantics): every datum is a point; the points of each series
        /// (the "detail" field, else the "color" field) are joined in x order by segments of "strokeWidth" mm.
        /// </summary>
        void ConnectLines(JSONNode specs)
        {
            string seriesField = specs["encoding"]["detail"]["field"] != null ? specs["encoding"]["detail"]["field"].Value
                               : specs["encoding"]["color"]["field"] != null ? specs["encoding"]["color"]["field"].Value : null;
            float stroke = (visSpecs["strokeWidth"] != null ? visSpecs["strokeWidth"].AsFloat : 6f) * SIZE_UNIT_SCALE_FACTOR;
            var series = new Dictionary<string, List<GameObject>>();
            var order = new List<string>();
            foreach (GameObject m in markInstances)
            {
                string key = seriesField != null ? m.GetComponent<Mark>().datum[seriesField] : "";
                if (!series.ContainsKey(key)) { series[key] = new List<GameObject>(); order.Add(key); }
                series[key].Add(m);
            }
            foreach (string key in order)
            {
                List<GameObject> pts = series[key];
                pts.Sort((a, b) => a.transform.localPosition.x.CompareTo(b.transform.localPosition.x));
                var r = pts[0].GetComponent<Renderer>();
                var mat = VLMCharts.Mats.Opaque(r != null ? r.material.color : Color.white);
                for (int i = 1; i < pts.Count; i++)
                    VLMCharts.Prims.Line("DataLine " + key, marksParentObject.transform,
                        pts[i - 1].transform.localPosition, pts[i].transform.localPosition, stroke, mat);
            }
        }

        // ------------------------------------------------------------------ guides
        void ConstructAxes(JSONNode specs)
        {
            foreach (ChannelEncoding ce in channelEncodings)
            {
                JSONNode axisSpecs = specs["encoding"][ce.channel]["axis"];
                if (axisSpecs != null && axisSpecs.Value.ToString() != "none" && (ce.channel == "x" || ce.channel == "y" || ce.channel == "z"))
                {
                    var go = new GameObject("Axis " + ce.channel);
                    go.transform.SetParent(guidesParentObject.transform, false);
                    ce.axis = go;
                    go.AddComponent<Axis>().Build(axisSpecs, ce.scale, GetVisSize());
                }
            }
        }

        void ConstructLegends(JSONNode specs)
        {
            foreach (ChannelEncoding ce in channelEncodings)
            {
                JSONNode legendSpecs = specs["encoding"][ce.channel]["legend"];
                if (legendSpecs != null && legendSpecs.Value.ToString() != "none" && ce.channel == "color")
                {
                    var go = new GameObject("Legend " + ce.channel);
                    go.transform.SetParent(guidesParentObject.transform, false);
                    ce.legend = go;
                    go.AddComponent<Legend>().Build(legendSpecs, ce, visSpecs["mark"].Value);
                }
            }
        }

        // "titlePosition": "back" (port extension) puts the title above the back edge — for charts viewed from above.
        void ConstructTitle()
        {
            if (string.IsNullOrEmpty(title)) return;
            float s = SIZE_UNIT_SCALE_FACTOR;
            var t = VLMCharts.TextLabel.Create("Title", guidesParentObject.transform,
                new Vector3(width * 0.5f * s, height * s + 0.13f, visSpecs["titlePosition"].Value == "back" ? depth * s : 0f), title, Axis.TitleHeight * 1.25f, Color.white,
                VLMCharts.TextLabel.HAlign.Center, true, true);
            t.bold = true;
        }
    }
}
