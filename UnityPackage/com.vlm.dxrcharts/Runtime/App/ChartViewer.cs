using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using DxRSimpleJSON;
using UnityEngine;
using UnityEngine.XR;

namespace VLMCharts
{
    /// <summary>
    /// Graph-only viewer for Meta Quest 2. Shows exactly one DxR chart (pie, bar or scatter) floating in
    /// front of you — no panels, no controller models, no lasers — so the Quest system recording contains
    /// only the graph for VLM table extraction.
    ///
    /// Charts are listed in StreamingAssets/DxRSpecs/charts.json (written by data_prep/prepare_charts.py).
    ///
    /// Controls (nothing is drawn for them)
    ///   A  / right stick →     next chart            Editor: → or .
    ///   B  / right stick ←     previous chart        Editor: ← or ,
    ///   X                      put chart in front of you again       Editor: R
    ///   Y                      slow turntable rotation on/off        Editor: T
    ///   Grip (hold)            move/turn the chart with your hand    Editor: hold G + mouse
    ///   Left stick ← →         turn the chart                        Editor: J / L
    ///   Left stick click       backdrop: grid room → dark → light    Editor: C
    /// A timestamped log of which chart was shown when is written to
    ///   {persistentDataPath}/graph_logs/log_yyyyMMdd-HHmmss.jsonl   (pull with data_prep tools / adb)
    /// </summary>
    public class ChartViewer : MonoBehaviour
    {
        [Header("Placement")]
        public float Distance = 1.0f;          // metres in front of the eyes
        public float DropBelowEyes = 0.05f;    // chart centre slightly below eye level
        [Header("Look")]
        public Backdrop StartBackdrop = Backdrop.GridRoom;   // immersive blue grid room by default
        public Color Background = new Color(0.08f, 0.09f, 0.11f);   // used by the Dark backdrop
        public Color LightBackground = new Color(0.94f, 0.95f, 0.96f);
        public float TurntableDegPerSec = 12f;
        [Header("Start")]
        public int StartIndex = 0;

        XRRig _rig;
        readonly DesktopSim _sim = new DesktopSim();
        Transform _anchor, _turn, _holder;
        DxR.Vis _vis;
        readonly List<string> _specs = new List<string>();
        readonly List<string> _ids = new List<string>();
        int _index = -1;
        bool _turntable;
        ControllerHand _grab;
        Vector3 _grabPos; Quaternion _grabRot;
        StreamWriter _log;
        DateTime _t0;
        TextLabel _error;
        Quaternion _baseView = Quaternion.identity;
        ImmersiveRoom _room;
        Backdrop _backdrop;

        void Awake()
        {
            // DxR parses numbers with the current culture; force "." decimals on every device.
            CultureInfo.DefaultThreadCurrentCulture = CultureInfo.InvariantCulture;
            CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;

            _rig = XRRig.Create(Background);
            _rig.HideHands();
            _anchor = new GameObject("Chart Anchor").transform;
            _turn = new GameObject("Turntable").transform; _turn.SetParent(_anchor, false);
            _holder = new GameObject("DxR Vis").transform; _holder.SetParent(_turn, false);
            _vis = _holder.gameObject.AddComponent<DxR.Vis>();
            _room = ImmersiveRoom.Create(null);
            OpenLog();
            SetBackdrop((Backdrop)Mathf.Clamp(PlayerPrefs.GetInt("dxrcharts_backdrop", (int)StartBackdrop), 0, 2), "startup");
        }

        IEnumerator Start()
        {
            LoadChartList();
            float t = 0f;   // wait up to 2 s for a valid head pose before placing the chart
            while (t < 2f && XRSettings.isDeviceActive && _rig.Cam.transform.localPosition == Vector3.zero) { t += Time.deltaTime; yield return null; }
            if (_specs.Count > 0) Show(Mathf.Clamp(PlayerPrefs.GetInt("dxrcharts_index", StartIndex), 0, _specs.Count - 1));
            ResetPlacement("startup");
        }

        void OnApplicationPause(bool p) { Log(p ? "app_pause" : "app_resume", null); }
        void OnApplicationQuit() { Log("app_quit", null); if (_log != null) _log.Dispose(); }

        // ------------------------------------------------------------------ charts
        void LoadChartList()
        {
            string path = Application.streamingAssetsPath + "/DxRSpecs/charts.json";
            try
            {
                JSONNode j = JSON.Parse(DxR.Parser.GetStringFromFile(path));
                foreach (JSONNode c in j["charts"].Children)
                {
                    _specs.Add(c["spec"].Value);
                    _ids.Add(c["id"] != null ? c["id"].Value : c["spec"].Value);
                }
            }
            catch (Exception e) { ShowError("Cannot read DxRSpecs/charts.json — run DxR Charts ▸ 3. Create scene + copy charts.\n" + e.Message); }
        }

        void Show(int index)
        {
            if (_specs.Count == 0) return;
            index = (index % _specs.Count + _specs.Count) % _specs.Count;
            _index = index;
            PlayerPrefs.SetInt("dxrcharts_index", index);
            ClearError();
            try
            {
                _vis.Load(_specs[index]);
                Vector3 size = _vis.GetVisSize() * DxR.Vis.SIZE_UNIT_SCALE_FACTOR;
                _holder.localPosition = -size * 0.5f;        // centre the chart on the anchor
                // optional spec key (port extension): "view": {"yaw": 30, "pitch": 0, "drop": 0.3} — initial 3/4 view for 3D charts
                DxRSimpleJSON.JSONNode view = _vis.InferredSpecs != null ? _vis.InferredSpecs["view"] : null;
                _baseView = Quaternion.Euler(view != null && view["pitch"] != null ? view["pitch"].AsFloat : 0f,
                                             view != null && view["yaw"] != null ? view["yaw"].AsFloat : 0f, 0f);
                _turn.localRotation = _baseView;
                // "drop" (m): lower this chart below the usual height so you look down onto it (3D bar grids)
                _turn.localPosition = Vector3.down * (view != null && view["drop"] != null ? view["drop"].AsFloat : 0f);
                Log("chart_shown", new Dictionary<string, object> {
                    { "index", index }, { "id", _ids[index] }, { "spec", _specs[index] },
                    { "title", _vis.Title }, { "marks", _vis.GetNumMarkInstances() }, { "backdrop", _backdrop.ToString() } });
            }
            catch (Exception e)
            {
                ShowError("Could not build " + _specs[index] + ":\n" + e.Message);
                Debug.LogException(e);
            }
        }

        // ------------------------------------------------------------------ frame loop
        void Update()
        {
            if (XRSettings.isDeviceActive) _rig.Poll(); else _sim.Update(_rig);
            ControllerHand R = _rig.Right, L = _rig.Left;

            if (R.Down(Btn.Primary) || R.Down(Btn.StickRight)) Show(_index + 1);
            if (R.Down(Btn.Secondary) || R.Down(Btn.StickLeft)) Show(_index - 1);
            if (L.Down(Btn.Primary)) ResetPlacement("button_X");
            if (L.Down(Btn.Secondary)) { _turntable = !_turntable; Log("turntable", new Dictionary<string, object> { { "on", _turntable } }); }

            if (L.Down(Btn.StickClick)) SetBackdrop((Backdrop)(((int)_backdrop + 1) % 3), "button_left_stick");
            if (Mathf.Abs(L.Stick.x) > 0.2f) _turn.Rotate(0f, -L.Stick.x * 60f * Time.deltaTime, 0f, Space.Self);
            if (_turntable) _turn.Rotate(0f, TurntableDegPerSec * Time.deltaTime, 0f, Space.Self);

            HandleGrab();
        }

        void HandleGrab()
        {
            if (_grab == null)
            {
                foreach (var h in new[] { _rig.Right, _rig.Left })
                    if (h.Tracked && h.Down(Btn.Grip))
                    {
                        _grab = h;
                        Vector3 hp = HandPos(h); Quaternion hr = HandRot(h);
                        _grabPos = Quaternion.Inverse(hr) * (_anchor.position - hp);
                        _grabRot = Quaternion.Inverse(hr) * _anchor.rotation;
                        break;
                    }
            }
            else
            {
                Vector3 hp = HandPos(_grab); Quaternion hr = HandRot(_grab);
                _anchor.position = hp + hr * _grabPos;
                _anchor.rotation = hr * _grabRot;
                if (!_grab.Held(Btn.Grip)) { _grab = null; Log("moved", null); }
            }
        }

        Vector3 HandPos(ControllerHand h) { return XRSettings.isDeviceActive ? _rig.GripWorldPos(h) : _rig.AimRay(h).origin; }
        Quaternion HandRot(ControllerHand h) { return XRSettings.isDeviceActive ? _rig.GripWorldRot(h) : _rig.TrackingSpace.rotation * h.AimRot; }

        void ResetPlacement(string source)
        {
            Transform head = _rig.Cam.transform;
            Vector3 fwd = head.forward; fwd.y = 0f;
            if (fwd.sqrMagnitude < 1e-4f) fwd = Vector3.forward;
            fwd.Normalize();
            _anchor.position = head.position + fwd * Distance + Vector3.down * DropBelowEyes;
            _anchor.rotation = Quaternion.LookRotation(fwd, Vector3.up);
            _turn.localRotation = _baseView;
            _grab = null;
            // align the room with the viewing direction, centred on you, floor at tracking-floor height
            _room.transform.position = new Vector3(head.position.x, _rig.TrackingSpace.position.y, head.position.z);
            _room.transform.rotation = Quaternion.LookRotation(fwd, Vector3.up);
            Log("reset_view", new Dictionary<string, object> { { "source", source } });
        }

        void SetBackdrop(Backdrop b, string source)
        {
            _backdrop = b;
            PlayerPrefs.SetInt("dxrcharts_backdrop", (int)b);
            _room.gameObject.SetActive(b == Backdrop.GridRoom);
            _rig.Cam.clearFlags = CameraClearFlags.SolidColor;
            _rig.Cam.backgroundColor = b == Backdrop.Light ? LightBackground : Background;
            Log("backdrop", new Dictionary<string, object> { { "backdrop", b.ToString() }, { "source", source } });
        }

        // ------------------------------------------------------------------ errors (only shown if a chart fails)
        void ShowError(string msg)
        {
            Debug.LogError("[DxRCharts] " + msg);
            if (_error == null)
                _error = TextLabel.Create("Error", _anchor, Vector3.zero, "", 0.025f, new Color(1f, 0.55f, 0.5f), TextLabel.HAlign.Center, true, true);
            _error.gameObject.SetActive(true);
            _error.Set(msg);
        }

        void ClearError() { if (_error != null) _error.gameObject.SetActive(false); }

        // ------------------------------------------------------------------ log
        void OpenLog()
        {
            try
            {
                string dir = Path.Combine(Application.persistentDataPath, "graph_logs");
                Directory.CreateDirectory(dir);
                _t0 = DateTime.UtcNow;
                _log = new StreamWriter(Path.Combine(dir, "log_" + DateTime.Now.ToString("yyyyMMdd-HHmmss", CultureInfo.InvariantCulture) + ".jsonl"), false, new UTF8Encoding(false)) { AutoFlush = true };
                Log("app_start", new Dictionary<string, object> { { "device", SystemInfo.deviceModel }, { "xr", XRSettings.loadedDeviceName } });
            }
            catch (Exception e) { Debug.LogWarning("[DxRCharts] log disabled: " + e.Message); }
        }

        void Log(string type, Dictionary<string, object> fields)
        {
            if (_log == null) return;
            var now = DateTime.UtcNow;
            var o = new JSONObject();
            o.Add("type", type);
            o.Add("t", Math.Round((now - _t0).TotalSeconds, 3));
            o.Add("utc", now.ToString("yyyy-MM-ddTHH:mm:ss.fffZ", CultureInfo.InvariantCulture));
            o.Add("local_time", DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff", CultureInfo.InvariantCulture));
            if (fields != null)
                foreach (var kv in fields)
                {
                    if (kv.Value is bool) o.Add(kv.Key, new JSONBool((bool)kv.Value));
                    else if (kv.Value is int) o.Add(kv.Key, new JSONNumber((int)kv.Value));
                    else o.Add(kv.Key, new JSONString(kv.Value == null ? "" : kv.Value.ToString()));
                }
            try { _log.WriteLine(o.ToString()); } catch { }
        }
    }
}
