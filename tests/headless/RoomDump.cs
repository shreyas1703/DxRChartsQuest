using System; using System.IO; using System.Text; using System.Globalization; using UnityEngine;
class RoomDump { static void Main(string[] a) {
  CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
  var r = VLMCharts.ImmersiveRoom.Create(null);
  var sb = new StringBuilder("{");
  bool firstMesh = true;
  foreach (Transform ch in r.transform) {
    var m = ch.GetComponent<MeshFilter>().sharedMesh;
    if (!firstMesh) sb.Append(","); firstMesh = false;
    sb.Append("\"" + ch.gameObject.name + "\":{\"v\":[");
    for (int i = 0; i < m.verts.Count; i++) { var v = m.verts[i]; var c = m.cols[i]; if (i > 0) sb.Append(","); sb.AppendFormat("[{0:0.###},{1:0.###},{2:0.###},{3:0.###},{4:0.###},{5:0.###}]", v.x, v.y, v.z, c.r, c.g, c.b); }
    sb.Append("],\"t\":[" + string.Join(",", m.tris) + "]}");
    Console.WriteLine(ch.gameObject.name + ": " + m.verts.Count + " verts, " + m.tris.Count / 3 + " tris");
  }
  File.WriteAllText(a[0], sb.Append("}").ToString());
} }
