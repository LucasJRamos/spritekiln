// SpriteKiln normal-mapped lighting for SpriteBatch (MonoGame 3.8, DesktopGL or WindowsDX).
// Add it to the content pipeline (Effect importer/processor) and draw the sprites of one sheet per batch:
//
//   lit.Parameters["MatrixTransform"].SetValue(view * Matrix.CreateOrthographicOffCenter(0, w, h, 0, 0, 1));
//   lit.Parameters["NormalMap"].SetValue(sheet.NormalMap);
//   lit.Parameters["Ambient"].SetValue(new Vector3(0.35f, 0.33f, 0.45f));
//   lit.Parameters["LightPos"].SetValue(new[] { new Vector3(x, y, 40) });     // px, same space as the sprites
//   lit.Parameters["LightColor"].SetValue(new[] { new Vector3(1f, 0.85f, 0.65f) });
//   lit.Parameters["LightRadius"].SetValue(new[] { 120f });
//   lit.Parameters["LightCount"].SetValue(1);
//   spriteBatch.Begin(samplerState: SamplerState.PointClamp, effect: lit);   // no transformMatrix: it is in MatrixTransform
//
// Normals are camera-space (x right, y up on screen, z toward the viewer), as SpriteKiln writes them. Sprites
// drawn with SpriteEffects.FlipHorizontally (mirrored directions) get their normals mirrored automatically.

#if OPENGL
    #define SV_POSITION POSITION
    #define VS_SHADERMODEL vs_3_0
    #define PS_SHADERMODEL ps_3_0
#else
    #define VS_SHADERMODEL vs_4_0
    #define PS_SHADERMODEL ps_4_0
#endif

#define MAX_LIGHTS 4

float4x4 MatrixTransform;
float3 Ambient = float3(1, 1, 1);
float3 LightPos[MAX_LIGHTS];      // x, y in the sprites' space (px), z = height above the ground plane (px)
float3 LightColor[MAX_LIGHTS];
float LightRadius[MAX_LIGHTS];
int LightCount = 0;

Texture2D SpriteTexture;
sampler2D SpriteSampler = sampler_state { Texture = <SpriteTexture>; };
Texture2D NormalMap;
sampler2D NormalSampler = sampler_state
{
    Texture = <NormalMap>;
    MinFilter = Point;
    MagFilter = Point;
    MipFilter = Point;
    AddressU = Clamp;
    AddressV = Clamp;
};

struct VSOutput
{
    float4 Position : SV_POSITION;
    float4 Color : COLOR0;
    float2 TexCoord : TEXCOORD0;
    float2 World : TEXCOORD1;
};

VSOutput MainVS(float4 position : POSITION0, float4 color : COLOR0, float2 texCoord : TEXCOORD0)
{
    VSOutput output;
    output.Position = mul(position, MatrixTransform);
    output.Color = color;
    output.TexCoord = texCoord;
    output.World = position.xy;
    return output;
}

float4 MainPS(VSOutput input) : COLOR0
{
    float4 color = tex2D(SpriteSampler, input.TexCoord) * input.Color;
    float3 n = tex2D(NormalSampler, input.TexCoord).rgb * 2 - 1;
    if (ddx(input.TexCoord.x) < 0)
        n.x = -n.x;   // the texture runs backwards: a horizontally flipped sprite
    float3 light = Ambient;
    for (int i = 0; i < MAX_LIGHTS; i++)
    {
        if (i < LightCount)
        {
            float3 d = LightPos[i] - float3(input.World, 0);
            d.y = -d.y;   // screen y grows down, the normals' y grows up
            float fall = saturate(1 - length(d.xy) / LightRadius[i]);
            light += LightColor[i] * saturate(dot(n, normalize(d))) * fall * fall;
        }
    }
    return float4(color.rgb * light, color.a);
}

technique Lit
{
    pass P0
    {
        VertexShader = compile VS_SHADERMODEL MainVS();
        PixelShader = compile PS_SHADERMODEL MainPS();
    }
};
