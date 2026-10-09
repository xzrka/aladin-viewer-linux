using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Media;

// WPF 가 family 이름을 물리 face 로 해석하는지 검사한다.
// TryGetGlyphTypeface=False 이면 그 이름은 WPF 내장 last-resort face(라틴 전용) 로
// 그려져 한글이 □ 가 된다. 설치 전 False → 설치 후 True 가 확인 목표.
class ProbeKr
{
    static string[] Names = {
        "Segoe UI", "Segoe UI Bold", "Segoe UI Light", "Segoe UI Semibold", "Segoe UI Symbol",
        "Segoe UI Emoji", "Malgun Gothic", "Gulim", "GulimChe", "Dotum", "DotumChe",
        "Batang", "Gungsuh", "Arial", "Arial Black", "Microsoft Sans Serif", "MS Sans Serif",
        "Tahoma", "Meiryo", "Yu Gothic UI", "NanumGothic", "NanumMyeongjo", "NanumPen",
        "UnDinaru", "SeoulNamsan", "SeoulHangangB", "CREMA_MYUNGJO2B",
        "Microsoft YaHei UI", "MS Gothic", "MS Mincho", "MS PGothic", "SimSun", "PMingLiU",
    };

    static void Probe(string label, FontFamily ff)
    {
        try
        {
            Typeface tf = new Typeface(ff, FontStyles.Normal, FontWeights.Normal, FontStretches.Normal);
            GlyphTypeface gt;
            bool ok = tf.TryGetGlyphTypeface(out gt);
            Console.WriteLine(label + ": Source=" + ff.Source + "  Baseline=" + ff.Baseline +
                              "  TryGetGlyphTypeface=" + ok);
            if (ok)
            {
                Console.Write("      Win32Family:");
                foreach (KeyValuePair<System.Globalization.CultureInfo, string> kv in gt.Win32FamilyNames)
                    Console.Write(" [" + kv.Key + "=" + kv.Value + "]");
                Console.WriteLine("  version=" + gt.Version);
            }
        }
        catch (Exception e)
        {
            Console.WriteLine(label + ": EXC " + e.GetType().Name + ": " + e.Message);
        }
    }

    [STAThread]
    static void Main()
    {
        try { Probe("SystemFonts.CaptionFontFamily", SystemFonts.CaptionFontFamily); }
        catch (Exception e) { Console.WriteLine("SystemFonts: EXC " + e.GetType().Name); }
        Console.WriteLine("SystemFontFamilies count=" + Fonts.SystemFontFamilies.Count);
        foreach (string n in Names) Probe("request '" + n + "'", new FontFamily(n));
    }
}
