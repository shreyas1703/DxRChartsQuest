using System.Collections.Generic;
using UnityEngine;
using UnityEngine.XR;

namespace VLMCharts
{
    public enum Hand { Left, Right }
    public enum Btn { Trigger, Grip, Primary, Secondary, Menu, StickClick, StickLeft, StickRight, StickUp, StickDown }

    /// <summary>
    /// One Quest Touch controller read through UnityEngine.XR.InputDevices (works with the OpenXR
    /// "Oculus Touch Controller Profile"). Provides pose, aim ray, button edges and haptics.
    /// </summary>
    public class ControllerHand
    {
        public readonly Hand Hand;
        public bool Tracked;
        public Vector3 GripPos, AimPos;          // tracking space
        public Quaternion GripRot = Quaternion.identity, AimRot = Quaternion.identity;
        public float Trigger, GripAxis;
        public Vector2 Stick;
        public Transform Visual;                 // world-space visual (child of rig)
        public Transform Laser;
        public Transform Reticle;

        readonly bool[] _now = new bool[10], _prev = new bool[10];
        InputDevice _dev;
        static readonly InputFeatureUsage<Vector3> PointerPosition = new InputFeatureUsage<Vector3>("PointerPosition");
        static readonly InputFeatureUsage<Quaternion> PointerRotation = new InputFeatureUsage<Quaternion>("PointerRotation");

        public ControllerHand(Hand h) { Hand = h; }

        public bool Down(Btn b) { return _now[(int)b] && !_prev[(int)b]; }
        public bool Up(Btn b) { return !_now[(int)b] && _prev[(int)b]; }
        public bool Held(Btn b) { return _now[(int)b]; }

        public void Poll()
        {
            System.Array.Copy(_now, _prev, _now.Length);
            if (!_dev.isValid) _dev = InputDevices.GetDeviceAtXRNode(Hand == Hand.Left ? XRNode.LeftHand : XRNode.RightHand);
            if (!_dev.isValid) { Tracked = false; System.Array.Clear(_now, 0, _now.Length); return; }

            bool tracked;
            Tracked = _dev.TryGetFeatureValue(CommonUsages.isTracked, out tracked) ? tracked : true;
            _dev.TryGetFeatureValue(CommonUsages.devicePosition, out GripPos);
            _dev.TryGetFeatureValue(CommonUsages.deviceRotation, out GripRot);
            Vector3 ap; Quaternion ar;
            if (_dev.TryGetFeatureValue(PointerPosition, out ap) && _dev.TryGetFeatureValue(PointerRotation, out ar) && ar != new Quaternion(0, 0, 0, 0))
            { AimPos = ap; AimRot = ar; }
            else { AimPos = GripPos; AimRot = GripRot * Quaternion.Euler(40f, 0f, 0f); }

            _dev.TryGetFeatureValue(CommonUsages.trigger, out Trigger);
            _dev.TryGetFeatureValue(CommonUsages.grip, out GripAxis);
            _dev.TryGetFeatureValue(CommonUsages.primary2DAxis, out Stick);
            bool v;
            // Hysteresis on the analog trigger/grip so a light touch does not flicker.
            _now[(int)Btn.Trigger] = _prev[(int)Btn.Trigger] ? Trigger > 0.35f : Trigger > 0.6f;
            _now[(int)Btn.Grip] = _prev[(int)Btn.Grip] ? GripAxis > 0.35f : GripAxis > 0.6f;
            _now[(int)Btn.Primary] = _dev.TryGetFeatureValue(CommonUsages.primaryButton, out v) && v;
            _now[(int)Btn.Secondary] = _dev.TryGetFeatureValue(CommonUsages.secondaryButton, out v) && v;
            _now[(int)Btn.Menu] = _dev.TryGetFeatureValue(CommonUsages.menuButton, out v) && v;
            _now[(int)Btn.StickClick] = _dev.TryGetFeatureValue(CommonUsages.primary2DAxisClick, out v) && v;
            _now[(int)Btn.StickLeft] = _prev[(int)Btn.StickLeft] ? Stick.x < -0.4f : Stick.x < -0.75f;
            _now[(int)Btn.StickRight] = _prev[(int)Btn.StickRight] ? Stick.x > 0.4f : Stick.x > 0.75f;
            _now[(int)Btn.StickUp] = _prev[(int)Btn.StickUp] ? Stick.y > 0.4f : Stick.y > 0.75f;
            _now[(int)Btn.StickDown] = _prev[(int)Btn.StickDown] ? Stick.y < -0.4f : Stick.y < -0.75f;
        }

        /// <summary>Desktop fallback: drive this hand from mouse/keyboard.</summary>
        public void SetSimulated(Vector3 aimPos, Quaternion aimRot, bool[] buttons, Vector2 stick)
        {
            System.Array.Copy(_now, _prev, _now.Length);
            Tracked = true;
            AimPos = GripPos = aimPos; AimRot = GripRot = aimRot; Stick = stick;
            for (int i = 0; i < _now.Length; i++) _now[i] = buttons[i];
            Trigger = buttons[(int)Btn.Trigger] ? 1 : 0; GripAxis = buttons[(int)Btn.Grip] ? 1 : 0;
        }

        public void Haptic(float amplitude = 0.4f, float seconds = 0.04f)
        {
            if (!_dev.isValid) return;
            HapticCapabilities caps;
            if (_dev.TryGetHapticCapabilities(out caps) && caps.supportsImpulse) _dev.SendHapticImpulse(0, amplitude, seconds);
        }
    }

    /// <summary>
    /// Minimal XR rig: tracking-space root, head-tracked camera, two controllers with laser pointers.
    /// No XR Interaction Toolkit dependency — only the OpenXR plugin is required.
    /// </summary>
    public class XRRig : MonoBehaviour
    {
        public Camera Cam;
        public Transform TrackingSpace;
        public ControllerHand Left = new ControllerHand(Hand.Left), Right = new ControllerHand(Hand.Right);
        public bool XRActive { get; private set; }
        public float DesktopEyeHeight = 1.6f;

        InputDevice _head;
        bool _originSet;

        public static XRRig Create(Color background)
        {
            var root = new GameObject("XR Rig");
            var rig = root.AddComponent<XRRig>();
            rig.TrackingSpace = new GameObject("Tracking Space").transform;
            rig.TrackingSpace.SetParent(root.transform, false);

            var old = Camera.main;
            if (old != null && old.transform.parent == null) Destroy(old.gameObject);
            var camGo = new GameObject("Main Camera");
            camGo.tag = "MainCamera";
            camGo.transform.SetParent(rig.TrackingSpace, false);
            rig.Cam = camGo.AddComponent<Camera>();
            rig.Cam.nearClipPlane = 0.02f;
            rig.Cam.farClipPlane = 100f;
            rig.Cam.clearFlags = CameraClearFlags.SolidColor;
            rig.Cam.backgroundColor = background;
            camGo.AddComponent<AudioListener>();

            rig.BuildHandVisual(rig.Left);
            rig.BuildHandVisual(rig.Right);
            return rig;
        }

        void BuildHandVisual(ControllerHand h)
        {
            var root = new GameObject(h.Hand + " Controller").transform;
            root.SetParent(TrackingSpace, false);
            h.Visual = root;
            var body = Prims.Box("body", root, new Vector3(0, 0, -0.01f), new Vector3(0.035f, 0.03f, 0.09f), Mats.Opaque(new Color(0.22f, 0.24f, 0.28f), 0.5f));
            body.transform.localRotation = Quaternion.Euler(-35f, 0, 0);
            Prims.Box("ring", root, new Vector3(0, 0.025f, 0.035f), new Vector3(0.06f, 0.012f, 0.03f), Mats.Opaque(new Color(0.35f, 0.38f, 0.44f), 0.5f));

            h.Laser = Prims.MeshObject("laser", TrackingSpace, Prims.CubeMesh, Mats.Transparent(new Color(1, 1, 1, 0.35f), 20)).transform;
            h.Reticle = Prims.MeshObject("reticle", TrackingSpace, Prims.SphereMesh, Mats.Opaque(Mats.Accent)).transform;
            h.Reticle.localScale = Vector3.one * 0.012f;
        }

        void OnEnable() { Application.onBeforeRender += OnBeforeRender; }
        void OnDisable() { Application.onBeforeRender -= OnBeforeRender; }

        void Start()
        {
            XRActive = XRSettings.isDeviceActive;
            if (!XRActive)
            {
                Cam.transform.localPosition = new Vector3(0, DesktopEyeHeight, 0);
                Debug.Log("[DxRCharts] No XR device active — desktop mode (mouse = right controller). See CONTROLS in README.");
            }
        }

        void TrySetFloorOrigin()
        {
            if (_originSet) return;
            var subs = new List<XRInputSubsystem>();
            SubsystemManager.GetSubsystems(subs);
            foreach (var s in subs)
            {
                if (!s.running) continue;
                s.TrySetTrackingOriginMode(TrackingOriginModeFlags.Floor);
                bool floor = s.GetTrackingOriginMode() == TrackingOriginModeFlags.Floor;
                TrackingSpace.localPosition = floor ? Vector3.zero : new Vector3(0, DesktopEyeHeight, 0);
                _originSet = true;
            }
        }

        /// <summary>Called by the app every frame before interaction logic.</summary>
        public void Poll()
        {
            XRActive = XRSettings.isDeviceActive;
            if (!XRActive) return;
            TrySetFloorOrigin();
            UpdateHead();
            Left.Poll();
            Right.Poll();
        }

        void UpdateHead()
        {
            if (!_head.isValid) _head = InputDevices.GetDeviceAtXRNode(XRNode.CenterEye);
            if (!_head.isValid) _head = InputDevices.GetDeviceAtXRNode(XRNode.Head);
            Vector3 p; Quaternion r;
            if (_head.isValid)
            {
                if (_head.TryGetFeatureValue(CommonUsages.centerEyePosition, out p) || _head.TryGetFeatureValue(CommonUsages.devicePosition, out p))
                    Cam.transform.localPosition = p;
                if (_head.TryGetFeatureValue(CommonUsages.centerEyeRotation, out r) || _head.TryGetFeatureValue(CommonUsages.deviceRotation, out r))
                    Cam.transform.localRotation = r;
            }
        }

        void OnBeforeRender()
        {
            if (!XRActive) return;
            UpdateHead();                         // late-latch the head pose to reduce judder
        }

        /// <summary>Hide controller models, lasers and reticles (graph-only recordings).</summary>
        public void HideHands()
        {
            foreach (var h in new[] { Left, Right })
            {
                if (h.Visual != null) h.Visual.gameObject.SetActive(false);
                if (h.Laser != null) h.Laser.gameObject.SetActive(false);
                if (h.Reticle != null) h.Reticle.gameObject.SetActive(false);
            }
        }

        public Ray AimRay(ControllerHand h)
        {
            Vector3 o = TrackingSpace.TransformPoint(h.AimPos);
            Vector3 d = TrackingSpace.rotation * (h.AimRot * Vector3.forward);
            return new Ray(o, d);
        }

        public Vector3 GripWorldPos(ControllerHand h) { return TrackingSpace.TransformPoint(h.GripPos); }
        public Quaternion GripWorldRot(ControllerHand h) { return TrackingSpace.rotation * h.GripRot; }

        /// <summary>Update controller model, laser and reticle. hitDistance &lt; 0 = nothing hit.</summary>
        public void DrawHand(ControllerHand h, float hitDistance, bool hovering, bool showLaser)
        {
            bool vis = h.Tracked;
            h.Visual.gameObject.SetActive(vis && XRActive);
            if (vis && XRActive)
            {
                h.Visual.localPosition = h.GripPos;
                h.Visual.localRotation = h.GripRot;
            }
            bool laser = vis && showLaser;
            h.Laser.gameObject.SetActive(laser);
            h.Reticle.gameObject.SetActive(laser && hitDistance > 0);
            if (!laser) return;
            var ray = AimRay(h);
            float len = hitDistance > 0 ? hitDistance : 3f;
            Vector3 a = TrackingSpace.InverseTransformPoint(ray.origin + ray.direction * (XRActive ? 0.02f : 0.25f));
            Vector3 b = TrackingSpace.InverseTransformPoint(ray.origin + ray.direction * len);
            Prims.SetLine(h.Laser, a, b, hovering ? 0.004f : 0.0025f);
            h.Laser.GetComponent<MeshRenderer>().sharedMaterial = hovering ? Mats.Transparent(new Color(1f, 0.88f, 0.3f, 0.8f), 20) : Mats.Transparent(new Color(1, 1, 1, 0.35f), 20);
            if (hitDistance > 0) h.Reticle.localPosition = b;
        }
    }
}
