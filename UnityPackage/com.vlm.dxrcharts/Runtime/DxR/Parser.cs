using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using DxRSimpleJSON;
using System;
using System.IO;

namespace DxR
{
    public class Parser
    {
        static string specsBaseDir = "/DxRSpecs/";
        static string dataBaseDir = "/DxRData/";

        /// <summary>
        ///  Read specifications in JSON file specified by specsFilename as 
        ///  well as data file (if needed) and expand to a JSONNode scene specs with the 
        ///  data represented as a JSON object.
        /// </summary>
        public void Parse(string specsFilename, out JSONNode visSpecs)
        {
            visSpecs = JSON.Parse(GetStringFromFile(GetFullSpecsPath(specsFilename)));

            // If the specs file is empty, provide the boiler plate data and marks specs.
            if(visSpecs == null)
            {
                CreateEmptyTemplateSpecs(specsFilename, ref visSpecs);
            }

            ExpandDataSpecs(ref visSpecs);
        }

        private void CreateEmptyTemplateSpecs(string specsFilename, ref JSONNode visSpecs)
        {
            JSONNode emptySpecs = new JSONObject();
            JSONNode dataSpecs = new JSONObject();
            dataSpecs.Add("url", new JSONString(DxR.Vis.UNDEFINED));
            emptySpecs.Add("data", dataSpecs);
            emptySpecs.Add("mark", new JSONString(DxR.Vis.UNDEFINED));

            visSpecs = emptySpecs;

            try { System.IO.File.WriteAllText(GetFullSpecsPath(specsFilename), emptySpecs.ToString(2)); } catch (Exception) { }
        }

        private void ExpandDataSpecs(ref JSONNode visSpecs)
        {
            if (visSpecs["data"].Value == DxR.Vis.UNDEFINED || visSpecs["data"]["url"].Value == DxR.Vis.UNDEFINED) return;

            if (visSpecs["data"]["url"] != null)
            {
                if(visSpecs["data"]["url"].Value == "inline")
                {
                    return;
                }

                visSpecs["data"].Add("values", CreateValuesSpecs(visSpecs["data"]["url"]));
            } else if(visSpecs["data"]["values"] != null)
            {
                visSpecs["data"].Add("url", new JSONString("inline"));
            }

            // TODO: Do some checks.
        }

        public JSONNode CreateValuesSpecs(string dataURL)
        {
            string dataFilename = GetFullDataPath(dataURL);
            string ext = Path.GetExtension(dataFilename);
            if (ext == ".json")
            {
                JSONNode valuesJSONNode = JSON.Parse(GetStringFromFile(dataFilename));
                return valuesJSONNode;
            }
            else if (ext == ".csv")
            {
                JSONNode valuesJSONNode = JSON.ParseCSV(GetStringFromFile(dataFilename));
                return valuesJSONNode;
            }
            else
            {
                throw new Exception("Cannot load file type" + ext);
            }
        }

        /// <summary>Optional override (used by the headless tests): returns file text for a full path.</summary>
        public static Func<string, string> FileReader = null;

        // [DxRCharts port] On Android (Quest) StreamingAssets live inside the APK (jar:file://...),
        // where File.ReadAllText fails, so read those through UnityWebRequest (small files; blocking is fine).
        public static string GetStringFromFile(string filename)
        {
            if (FileReader != null) return FileReader(filename);
            if (filename.Contains("://") || filename.StartsWith("jar:"))
            {
                using (var req = UnityEngine.Networking.UnityWebRequest.Get(filename))
                {
                    var op = req.SendWebRequest();
                    while (!op.isDone) System.Threading.Thread.Sleep(1);
                    if (req.result != UnityEngine.Networking.UnityWebRequest.Result.Success)
                        throw new Exception("Cannot read " + filename + ": " + req.error);
                    return req.downloadHandler.text;
                }
            }
            return File.ReadAllText(filename);
        }

        public static string GetFullSpecsPath(string filename)
        {
            return Application.streamingAssetsPath + specsBaseDir + filename;
        }

        public static string GetFullDataPath(string filename)
        {
            return Application.streamingAssetsPath + dataBaseDir + filename;
        }

        internal List<string> GetDataFieldsList(string dataURL)
        {
            List<string> fieldNames = new List<string>();
            JSONNode dataSpecs = new JSONObject();
            string filename = GetFullDataPath(dataURL);

            string ext = Path.GetExtension(filename);
            if (ext == ".json")
            {
                JSONNode valuesJSONNode = JSON.Parse(GetStringFromFile(filename));
                dataSpecs.Add("values", valuesJSONNode);
            }
            else if (ext == ".csv")
            {
                JSONNode valuesJSONNode = JSON.ParseCSV(GetStringFromFile(filename));
                dataSpecs.Add("values", valuesJSONNode);
            }
            
            foreach (KeyValuePair<string, JSONNode> kvp in dataSpecs["values"][0].AsObject)
            {
                fieldNames.Add(kvp.Key);
            }

            return fieldNames;
        }

        internal List<string> GetDataFieldsListFromValues(JSONNode valuesSpecs)
        {
            List<string> fieldNames = new List<string>(); 
            foreach (KeyValuePair<string, JSONNode> kvp in valuesSpecs[0].AsObject)
            {
                fieldNames.Add(kvp.Key);
            }

            return fieldNames;
        }
    }
}

