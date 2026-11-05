using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.PackageManager;
using UnityEditor.PackageManager.Requests;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

namespace VLMCharts.EditorTools
{
    /// <summary>
    /// Menu "DxR Charts" — one-click project setup and builds for Quest 2.
    /// XR packages are touched through reflection so this plugin compiles even before OpenXR is installed.
    /// </summary>
    public static class DxRChartsSetup
    {
        const string Menu = "DxR Charts/";
        public const string PackageId = "com.vlm.dxrcharts";
        const string AppScene = "Assets/DxRCharts/Scenes/DxRCharts.unity";
        const string SpecsDir = "Assets/StreamingAssets/DxRSpecs";
        const string DataDir = "Assets/StreamingAssets/DxRData";
        const string ApkPath = "Builds/DxRCharts.apk";

        // ------------------------------------------------------------------ 1. packages
        static AddRequest _add;
        static readonly Queue<string> _toAdd = new Queue<string>();

        [MenuItem(Menu + "1. Install XR packages (OpenXR)", priority = 1)]
        public static void InstallPackages()
        {
            _toAdd.Clear();
            _toAdd.Enqueue("com.unity.xr.management");
            _toAdd.Enqueue("com.unity.xr.openxr");
            _toAdd.Enqueue("com.unity.inputsystem");
            NextPackage();
        }

        static void NextPackage()
        {
            if (_toAdd.Count == 0) { Debug.Log("[DxRCharts] XR packages installed. Next: DxR Charts ▸ 2. Configure project for Quest 2."); return; }
            string id = _toAdd.Dequeue();
            Debug.Log("[DxRCharts] Installing " + id + " …");
            _add = Client.Add(id);
            EditorApplication.update += PollAdd;
        }

        static void PollAdd()
        {
            if (_add == null || !_add.IsCompleted) return;
            EditorApplication.update -= PollAdd;
            if (_add.Status == StatusCode.Success) Debug.Log("[DxRCharts] Installed " + _add.Result.packageId);
            else Debug.LogError("[DxRCharts] Package install failed: " + (_add.Error != null ? _add.Error.message : "unknown"));
            _add = null;
            NextPackage();
        }

        // ------------------------------------------------------------------ 2. project configuration
        [MenuItem(Menu + "2. Configure project for Quest 2", priority = 2)]
        public static void ConfigureProject()
        {
            var log = new StringBuilder("[DxRCharts] Project configuration:\n");
            if (EditorUserBuildSettings.activeBuildTarget != BuildTarget.Android)
            {
                bool ok = EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android);
                log.AppendLine(ok ? " • switched build target to Android" : " ! could not switch to Android — install 'Android Build Support' (with OpenJDK + SDK & NDK) in Unity Hub");
            }
            var nbt = NamedBuildTarget.Android;
            if (PlayerSettings.productName == "New Unity Project" || string.IsNullOrEmpty(PlayerSettings.productName) || PlayerSettings.productName.StartsWith("My project")) PlayerSettings.productName = "DxRCharts";
            if (PlayerSettings.companyName == "DefaultCompany") PlayerSettings.companyName = "VLMCharts";
            string appId = PlayerSettings.GetApplicationIdentifier(nbt);
            if (string.IsNullOrEmpty(appId) || appId.StartsWith("com.DefaultCompany") || appId.StartsWith("com.Unity")) PlayerSettings.SetApplicationIdentifier(nbt, PackageId);
            log.AppendLine(" • package id: " + PlayerSettings.GetApplicationIdentifier(nbt));

            PlayerSettings.SetScriptingBackend(nbt, ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            PlayerSettings.Android.minSdkVersion = (AndroidSdkVersions)29;   // Quest requires API 29+
            PlayerSettings.colorSpace = ColorSpace.Linear;
            PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android, false);
            PlayerSettings.SetGraphicsAPIs(BuildTarget.Android, new[] { GraphicsDeviceType.Vulkan, GraphicsDeviceType.OpenGLES3 });
            PlayerSettings.defaultInterfaceOrientation = UIOrientation.LandscapeLeft;
            EditorUserBuildSettings.androidBuildSubtarget = MobileTextureSubtarget.ASTC;
            log.AppendLine(" • IL2CPP, ARM64, min API 29, Linear, Vulkan+GLES3, landscape, ASTC");

            // MSAA 4x makes thin text and lines far more legible (in the headset and in the recording)
            int q = QualitySettings.GetQualityLevel();
            for (int i = 0; i < QualitySettings.names.Length; i++) { QualitySettings.SetQualityLevel(i, false); QualitySettings.antiAliasing = 4; }
            QualitySettings.SetQualityLevel(q, false);
            SetUrpMsaa(4, log);

            ConfigureXR(BuildTargetGroup.Android, log, true);
            if (Application.platform == RuntimePlatform.WindowsEditor)
                ConfigureXR(BuildTargetGroup.Standalone, log, false);   // lets you press Play with Quest Link (Windows only)
            else
                log.AppendLine(" • Standalone (Editor Play mode) left without XR: no Quest Link on this OS — Play mode runs the mouse/keyboard simulator");
            AssetDatabase.SaveAssets();
            log.AppendLine("Next: Project Settings ▸ XR Plug-in Management ▸ Project Validation ▸ 'Fix All', then DxR Charts ▸ 3. Create scenes.");
            Debug.Log(log.ToString());
        }

        static void SetUrpMsaa(int samples, StringBuilder log)
        {
            var assets = new List<RenderPipelineAsset>();
            if (GraphicsSettings.defaultRenderPipeline != null) assets.Add(GraphicsSettings.defaultRenderPipeline);
            for (int i = 0; i < QualitySettings.names.Length; i++)
            {
                var a = QualitySettings.GetRenderPipelineAssetAt(i);
                if (a != null && !assets.Contains(a)) assets.Add(a);
            }
            foreach (var a in assets)
            {
                var p = a.GetType().GetProperty("msaaSampleCount", BindingFlags.Public | BindingFlags.Instance);
                if (p != null && p.CanWrite) { p.SetValue(a, samples); EditorUtility.SetDirty(a); log.AppendLine(" • URP asset '" + a.name + "' MSAA " + samples + "x"); }
            }
        }

        // ---- XR Plug-in Management + OpenXR via reflection
        static Type T(string fullName, string asm) { return Type.GetType(fullName + ", " + asm); }

        static void ConfigureXR(BuildTargetGroup group, StringBuilder log, bool required)
        {
            var perBt = T("UnityEditor.XR.Management.XRGeneralSettingsPerBuildTarget", "Unity.XR.Management.Editor");
            var metaStore = T("UnityEditor.XR.Management.Metadata.XRPackageMetadataStore", "Unity.XR.Management.Editor");
            var openXRSettings = T("UnityEngine.XR.OpenXR.OpenXRSettings", "Unity.XR.OpenXR");
            if (perBt == null || metaStore == null || openXRSettings == null)
            {
                log.AppendLine(" ! XR Management / OpenXR not installed — run DxR Charts ▸ 1. Install XR packages first.");
                return;
            }
            // Ensure the XR settings asset exists
            object perBtInst = null;
            UnityEngine.Object cfg;
            if (EditorBuildSettings.TryGetConfigObject("com.unity.xr.management.loader_settings", out cfg)) perBtInst = cfg;
            if (perBtInst == null)
            {
                var getOrCreate = perBt.GetMethod("GetOrCreate", BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
                if (getOrCreate != null) perBtInst = getOrCreate.Invoke(null, null);
            }
            if (perBtInst == null)
            {
                log.AppendLine(" ! Open Project Settings ▸ XR Plug-in Management once (it creates its settings), then run this menu again.");
                SettingsService.OpenProjectSettings("Project/XR Plug-in Management");
                return;
            }
            var hasSettings = perBt.GetMethod("HasSettingsForBuildTarget");
            if (hasSettings != null && !(bool)hasSettings.Invoke(perBtInst, new object[] { group }))
            {
                var create = perBt.GetMethod("CreateDefaultSettingsForBuildTarget");
                if (create != null) create.Invoke(perBtInst, new object[] { group });
            }
            var hasMgr = perBt.GetMethod("HasManagerSettingsForBuildTarget");
            if (hasMgr != null && !(bool)hasMgr.Invoke(perBtInst, new object[] { group }))
            {
                var createMgr = perBt.GetMethod("CreateDefaultManagerSettingsForBuildTarget");
                if (createMgr != null) createMgr.Invoke(perBtInst, new object[] { group });
            }
            var forBt = perBt.GetMethod("XRGeneralSettingsForBuildTarget", BindingFlags.Static | BindingFlags.Public);
            var general = forBt != null ? forBt.Invoke(null, new object[] { group }) : null;
            if (general == null) { log.AppendLine(" ! No XR settings for " + group + " — tick OpenXR manually in XR Plug-in Management."); return; }
            var managerProp = general.GetType().GetProperty("Manager") ?? general.GetType().GetProperty("AssignedSettings");
            var manager = managerProp != null ? managerProp.GetValue(general) : null;
            var initOnStart = general.GetType().GetProperty("InitManagerOnStart");
            if (initOnStart != null && initOnStart.CanWrite) initOnStart.SetValue(general, true);
            if (manager != null)
            {
                var assign = metaStore.GetMethod("AssignLoader", BindingFlags.Static | BindingFlags.Public);
                bool ok = assign != null && (bool)assign.Invoke(null, new object[] { manager, "UnityEngine.XR.OpenXR.OpenXRLoader", group });
                log.AppendLine(ok ? " • OpenXR loader enabled for " + group : " ! could not assign OpenXR loader for " + group + " (tick it manually)");
                EditorUtility.SetDirty((UnityEngine.Object)manager);
            }

            // OpenXR features: Meta Quest support + Oculus Touch controller profile
            var getSettings = openXRSettings.GetMethod("GetSettingsForBuildTargetGroup", BindingFlags.Static | BindingFlags.Public);
            var settings = getSettings != null ? getSettings.Invoke(null, new object[] { group }) as UnityEngine.Object : null;
            if (settings == null) { log.AppendLine(" ! OpenXR settings for " + group + " not found yet — reopen XR Plug-in Management and run again."); return; }
            var getFeatures = openXRSettings.GetMethods().FirstOrDefault(m => m.Name == "GetFeatures" && !m.IsGenericMethodDefinition && m.GetParameters().Length == 0);
            var features = getFeatures != null ? getFeatures.Invoke(settings, null) as Array : null;
            var want = required ? new[] { "MetaQuestFeature", "OculusTouchControllerProfile" } : new[] { "OculusTouchControllerProfile" };
            var enabledNow = new List<string>();
            if (features != null)
                foreach (var f in features)
                {
                    if (f == null) continue;
                    string n = f.GetType().Name;
                    if (Array.IndexOf(want, n) < 0) continue;
                    var en = f.GetType().GetProperty("enabled");
                    if (en != null) { en.SetValue(f, true); EditorUtility.SetDirty((UnityEngine.Object)f); enabledNow.Add(n); }
                }
            foreach (var w in want)
                log.AppendLine(enabledNow.Contains(w) ? " • OpenXR feature enabled (" + group + "): " + w : " ! OpenXR feature " + w + " not found for " + group + " — enable it under OpenXR ▸ Features / Interaction Profiles");
            EditorUtility.SetDirty(settings);
        }

        [MenuItem(Menu + "Advanced/Use Multi-pass stereo (if anything renders in one eye only)", priority = 60)]
        public static void UseMultiPass() { SetRenderMode("MultiPass"); }
        [MenuItem(Menu + "Advanced/Use Single-pass instanced stereo (default)", priority = 61)]
        public static void UseSinglePass() { SetRenderMode("SinglePassInstanced"); }

        static void SetRenderMode(string mode)
        {
            var openXRSettings = T("UnityEngine.XR.OpenXR.OpenXRSettings", "Unity.XR.OpenXR");
            if (openXRSettings == null) { Debug.LogError("[DxRCharts] OpenXR not installed."); return; }
            var settings = openXRSettings.GetMethod("GetSettingsForBuildTargetGroup").Invoke(null, new object[] { BuildTargetGroup.Android }) as UnityEngine.Object;
            var prop = openXRSettings.GetProperty("renderMode");
            if (settings == null || prop == null) { Debug.LogError("[DxRCharts] OpenXR settings not found."); return; }
            prop.SetValue(settings, Enum.Parse(prop.PropertyType, mode));
            EditorUtility.SetDirty(settings);
            AssetDatabase.SaveAssets();
            Debug.Log("[DxRCharts] OpenXR Android render mode = " + mode);
        }

        // ------------------------------------------------------------------ 3. scene + chart files
        [MenuItem(Menu + "3. Create scene + copy charts", priority = 3)]
        public static void CreateScene()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            Directory.CreateDirectory("Assets/DxRCharts/Scenes");
            CopyCharts();
            var app = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            new GameObject("DxR Chart Viewer").AddComponent<ChartViewer>();
            EditorSceneManager.SaveScene(app, AppScene);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(AppScene, true) };
            AssetDatabase.Refresh();
            Debug.Log("[DxRCharts] Created " + AppScene + ". Press Play (mouse/keyboard) or build to the Quest.");
        }

        public static string PackageRoot()
        {
            var info = UnityEditor.PackageManager.PackageInfo.FindForAssembly(typeof(DxRChartsSetup).Assembly);
            if (info != null && !string.IsNullOrEmpty(info.resolvedPath)) return info.resolvedPath;
            return Path.GetFullPath("Packages/com.vlm.dxrcharts");
        }

        /// <summary>Copies Charts~/DxRSpecs and Charts~/DxRData (written by data_prep/prepare_charts.py) into StreamingAssets.</summary>
        [MenuItem(Menu + "Copy charts to StreamingAssets", priority = 30)]
        public static void CopyCharts()
        {
            int n = CopyDir(Path.Combine(PackageRoot(), "Charts~/DxRSpecs"), SpecsDir) + CopyDir(Path.Combine(PackageRoot(), "Charts~/DxRData"), DataDir);
            AssetDatabase.Refresh();
            Debug.Log("[DxRCharts] Copied " + n + " chart files to StreamingAssets (DxRSpecs + DxRData).");
        }

        static int CopyDir(string src, string dst)
        {
            if (!Directory.Exists(src)) { Debug.LogWarning("[DxRCharts] missing " + src); return 0; }
            Directory.CreateDirectory(dst);
            int n = 0;
            foreach (var f in Directory.GetFiles(src))
            {
                string ext = Path.GetExtension(f).ToLowerInvariant();
                if (ext != ".csv" && ext != ".json") continue;
                File.Copy(f, Path.Combine(dst, Path.GetFileName(f)), true);
                n++;
            }
            // Remove charts that are no longer in the package (e.g. an older bar chart), so the folders match Charts~.
            foreach (var f in Directory.GetFiles(dst))
            {
                string ext = Path.GetExtension(f).ToLowerInvariant();
                if ((ext == ".csv" || ext == ".json") && !File.Exists(Path.Combine(src, Path.GetFileName(f))))
                {
                    File.Delete(f);
                    if (File.Exists(f + ".meta")) File.Delete(f + ".meta");
                }
            }
            return n;
        }

        // ------------------------------------------------------------------ 4. build
        [MenuItem(Menu + "4. Build and Run on Quest", priority = 4)]
        public static void BuildAndRun() { Build(true); }
        [MenuItem(Menu + "Build APK only (no headset needed)", priority = 5)]
        public static void BuildOnly() { Build(false); }

        static void Build(bool run)
        {
            if (!File.Exists(AppScene)) { Debug.LogError("[DxRCharts] " + AppScene + " missing — run DxR Charts ▸ 3 first."); return; }
            if (EditorUserBuildSettings.activeBuildTarget != BuildTarget.Android) { Debug.LogError("[DxRCharts] Switch to Android first (DxR Charts ▸ 2)."); return; }
            CopyCharts();
            Directory.CreateDirectory(Path.GetDirectoryName(ApkPath));
            var opts = new BuildPlayerOptions
            {
                scenes = new[] { AppScene },
                locationPathName = ApkPath,
                target = BuildTarget.Android,
                targetGroup = BuildTargetGroup.Android,
                options = run ? BuildOptions.AutoRunPlayer : BuildOptions.None
            };
            EditorUserBuildSettings.buildAppBundle = false;
            var report = BuildPipeline.BuildPlayer(opts);
            if (report.summary.result == BuildResult.Succeeded)
                Debug.Log("[DxRCharts] Built " + ApkPath + (run ? " and launched on the headset." : ". Install: adb install -r " + ApkPath));
            else Debug.LogError("[DxRCharts] Build failed: " + report.summary.result + " — see the first red error in the Console.");
        }

        // ------------------------------------------------------------------ checks
        [MenuItem(Menu + "Check setup", priority = 20)]
        public static void CheckSetup()
        {
            var sb = new StringBuilder("[DxRCharts] Setup check:\n");
            Check(sb, EditorUserBuildSettings.activeBuildTarget == BuildTarget.Android, "Build target is Android");
            Check(sb, PlayerSettings.GetScriptingBackend(NamedBuildTarget.Android) == ScriptingImplementation.IL2CPP, "IL2CPP scripting backend");
            Check(sb, (PlayerSettings.Android.targetArchitectures & AndroidArchitecture.ARM64) != 0, "ARM64 architecture");
            Check(sb, (int)PlayerSettings.Android.minSdkVersion >= 29, "Minimum API level >= 29");
            Check(sb, T("UnityEngine.XR.OpenXR.OpenXRLoader", "Unity.XR.OpenXR") != null, "OpenXR package installed");
            Check(sb, File.Exists(AppScene), "Chart scene exists");
            Check(sb, File.Exists(Path.Combine(SpecsDir, "charts.json")), "charts.json in StreamingAssets/DxRSpecs");
            Check(sb, EditorBuildSettings.scenes.Any(s => s.path == AppScene && s.enabled), "Chart scene in Build Settings");
            sb.AppendLine("Also confirm Project Settings > XR Plug-in Management (Android): OpenXR + Meta Quest feature group ticked, Project Validation clean.");
            Debug.Log(sb.ToString());
        }

        static void Check(StringBuilder sb, bool ok, string what) { sb.Append(ok ? "  [OK]   " : "  [FIX]  ").AppendLine(what); }

        [MenuItem(Menu + "Open Editor graph logs folder", priority = 40)]
        public static void OpenPersistent() { EditorUtility.RevealInFinder(Application.persistentDataPath); }
    }
}
