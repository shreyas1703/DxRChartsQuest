// Opaque color with optional fake directional shading. Works in URP and Built-in,
// single-pass-instanced and multi-pass stereo.
Shader "DxRCharts/Unlit"
{
    Properties
    {
        _Color ("Color", Color) = (1,1,1,1)
        _Shade ("Shade amount", Range(0,1)) = 0.45
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "UnityCG.cginc"
            fixed4 _Color;
            half _Shade;
            struct appdata { float4 vertex : POSITION; float3 normal : NORMAL; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct v2f { float4 pos : SV_POSITION; half3 n : TEXCOORD0; UNITY_VERTEX_OUTPUT_STEREO };
            v2f vert (appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.pos = UnityObjectToClipPos(v.vertex);
                o.n = UnityObjectToWorldNormal(v.normal);
                return o;
            }
            fixed4 frag (v2f i) : SV_Target
            {
                half l = saturate(dot(normalize(i.n), normalize(half3(0.35, 0.8, -0.45))));
                half k = lerp(1.0, 0.55 + 0.45 * l, _Shade);
                return fixed4(_Color.rgb * k, 1);
            }
            ENDCG
        }
    }
}
