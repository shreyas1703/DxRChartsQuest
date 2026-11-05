using UnityEngine;
#if DXRCHARTS_INPUTSYSTEM && ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace VLMCharts
{
    /// <summary>
    /// Mouse + keyboard stand-in for the controllers, so the whole app can be tested in the Editor
    /// without a headset (Play mode with no XR device active).
    ///   Right-mouse drag: look      WASD/QE: move          Left click: trigger (select / press button)
    ///   G or middle mouse: grip (grab chart)   → / . : A (next year)   ← / , : B (previous year)
    ///   R: X (reset view)   T: Y (label size)   J/L: rotate chart   I/K: scale chart   C: chart type
    ///   V: toggle 'Quest recording view' (90° field of view — pair it with a 1024×1024 Game view to judge
    ///      label readability roughly as the Quest's system video will show it)
    /// </summary>
    public class DesktopSim
    {
        float _yaw, _pitch;
        bool _vPrev;
        public bool QuestView { get; private set; }
        public const float NormalFov = 60f, QuestFov = 90f;
        readonly bool[] _r = new bool[10], _l = new bool[10];

        enum K { W, A, S, D, Q, E, G, R, T, J, L, I, Kk, Right, Left, Period, Comma, C, V }

        public void Update(XRRig rig)
        {
            var cam = rig.Cam.transform;
            bool v = Key(K.V);
            if (v && !_vPrev)
            {
                QuestView = !QuestView;
                Debug.Log("[DxRCharts] " + (QuestView ? "Quest recording view ON (90° FOV). Set the Game view to 1024x1024 for a realistic preview." : "Quest recording view OFF."));
            }
            _vPrev = v;
            rig.Cam.fieldOfView = QuestView ? QuestFov : NormalFov;
            if (Mouse(1))
            {
                Vector2 d = MouseDelta();
                _yaw += d.x * 0.15f; _pitch = Mathf.Clamp(_pitch - d.y * 0.15f, -80f, 80f);
            }
            cam.localRotation = Quaternion.Euler(_pitch, _yaw, 0);
            Vector3 mv = Vector3.zero;
            if (Key(K.W)) mv += Vector3.forward; if (Key(K.S)) mv += Vector3.back;
            if (Key(K.A)) mv += Vector3.left; if (Key(K.D)) mv += Vector3.right;
            if (Key(K.E)) mv += Vector3.up; if (Key(K.Q)) mv += Vector3.down;
            cam.localPosition += Quaternion.Euler(0, _yaw, 0) * mv * Time.deltaTime * 1.2f;

            Ray ray = rig.Cam.ScreenPointToRay(MousePos());
            Vector3 aimPos = rig.TrackingSpace.InverseTransformPoint(ray.origin);
            Quaternion aimRot = Quaternion.Inverse(rig.TrackingSpace.rotation) * Quaternion.LookRotation(ray.direction, cam.up);

            System.Array.Clear(_r, 0, _r.Length); System.Array.Clear(_l, 0, _l.Length);
            _r[(int)Btn.Trigger] = Mouse(0);
            _r[(int)Btn.Grip] = Mouse(2) || Key(K.G);
            _r[(int)Btn.Primary] = Key(K.Right) || Key(K.Period);
            _r[(int)Btn.Secondary] = Key(K.Left) || Key(K.Comma);
            _l[(int)Btn.Primary] = Key(K.R);
            _l[(int)Btn.Secondary] = Key(K.T);
            _l[(int)Btn.StickClick] = Key(K.C);
            Vector2 stick = new Vector2((Key(K.L) ? 1 : 0) - (Key(K.J) ? 1 : 0), (Key(K.I) ? 1 : 0) - (Key(K.Kk) ? 1 : 0));
            rig.Right.SetSimulated(aimPos, aimRot, _r, Vector2.zero);
            rig.Left.SetSimulated(aimPos, aimRot, _l, stick);
        }

#if DXRCHARTS_INPUTSYSTEM && ENABLE_INPUT_SYSTEM
        static bool Mouse(int b)
        {
            var m = UnityEngine.InputSystem.Mouse.current; if (m == null) return false;
            return b == 0 ? m.leftButton.isPressed : b == 1 ? m.rightButton.isPressed : m.middleButton.isPressed;
        }
        static Vector2 MouseDelta() { var m = UnityEngine.InputSystem.Mouse.current; return m == null ? Vector2.zero : m.delta.ReadValue(); }
        static Vector3 MousePos() { var m = UnityEngine.InputSystem.Mouse.current; return m == null ? Vector3.zero : (Vector3)m.position.ReadValue(); }
        static bool Key(K k)
        {
            var kb = Keyboard.current; if (kb == null) return false;
            switch (k)
            {
                case K.W: return kb.wKey.isPressed; case K.A: return kb.aKey.isPressed; case K.S: return kb.sKey.isPressed;
                case K.D: return kb.dKey.isPressed; case K.Q: return kb.qKey.isPressed; case K.E: return kb.eKey.isPressed;
                case K.G: return kb.gKey.isPressed; case K.R: return kb.rKey.isPressed; case K.T: return kb.tKey.isPressed;
                case K.J: return kb.jKey.isPressed; case K.L: return kb.lKey.isPressed; case K.I: return kb.iKey.isPressed;
                case K.Kk: return kb.kKey.isPressed; case K.Right: return kb.rightArrowKey.isPressed; case K.Left: return kb.leftArrowKey.isPressed;
                case K.Period: return kb.periodKey.isPressed; case K.Comma: return kb.commaKey.isPressed; case K.C: return kb.cKey.isPressed; case K.V: return kb.vKey.isPressed;
            }
            return false;
        }
#elif ENABLE_LEGACY_INPUT_MANAGER
        static bool Mouse(int b) { return Input.GetMouseButton(b); }
        static Vector2 MouseDelta() { return new Vector2(Input.GetAxis("Mouse X"), Input.GetAxis("Mouse Y")) * 10f; }
        static Vector3 MousePos() { return Input.mousePosition; }
        static bool Key(K k)
        {
            switch (k)
            {
                case K.W: return Input.GetKey(KeyCode.W); case K.A: return Input.GetKey(KeyCode.A); case K.S: return Input.GetKey(KeyCode.S);
                case K.D: return Input.GetKey(KeyCode.D); case K.Q: return Input.GetKey(KeyCode.Q); case K.E: return Input.GetKey(KeyCode.E);
                case K.G: return Input.GetKey(KeyCode.G); case K.R: return Input.GetKey(KeyCode.R); case K.T: return Input.GetKey(KeyCode.T);
                case K.J: return Input.GetKey(KeyCode.J); case K.L: return Input.GetKey(KeyCode.L); case K.I: return Input.GetKey(KeyCode.I);
                case K.Kk: return Input.GetKey(KeyCode.K); case K.Right: return Input.GetKey(KeyCode.RightArrow); case K.Left: return Input.GetKey(KeyCode.LeftArrow);
                case K.Period: return Input.GetKey(KeyCode.Period); case K.Comma: return Input.GetKey(KeyCode.Comma); case K.C: return Input.GetKey(KeyCode.C); case K.V: return Input.GetKey(KeyCode.V);
            }
            return false;
        }
#else
        static bool Mouse(int b) { return false; }
        static Vector2 MouseDelta() { return Vector2.zero; }
        static Vector3 MousePos() { return Vector3.zero; }
        static bool Key(K k) { return false; }
#endif
    }
}
