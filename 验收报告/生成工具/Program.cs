using System.Text.Json;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Validation;
using DocumentFormat.OpenXml.Wordprocessing;
using MiniMaxAIDocx.Core.Samples;
using A = DocumentFormat.OpenXml.Drawing;
using DW = DocumentFormat.OpenXml.Drawing.Wordprocessing;
using PIC = DocumentFormat.OpenXml.Drawing.Pictures;

if (args.Length != 2) throw new ArgumentException("Usage: DocBuilder content.json output.docx");
var source = Path.GetFullPath(args[0]);
var target = Path.GetFullPath(args[1]);
using var data = JsonDocument.Parse(File.ReadAllText(source));
var root = data.RootElement;
Directory.CreateDirectory(Path.GetDirectoryName(target)!);
AestheticRecipeSamples.CreateAcademicThesisDocument(target);
using (var doc = WordprocessingDocument.Open(target, true))
{
    var main = doc.MainDocumentPart!;
    var body = main.Document.Body!;
    var sect = (SectionProperties)body.Elements<SectionProperties>().Last().CloneNode(true);
    body.RemoveAllChildren();
    sect.GetFirstChild<PageSize>()!.Width = 11906U;
    sect.GetFirstChild<PageSize>()!.Height = 16838U;
    foreach (var footer in main.FooterParts)
        foreach (var p in footer.Footer.Elements<Paragraph>())
            p.ParagraphProperties = new ParagraphProperties(new Justification { Val = JustificationValues.Center });
    foreach (var heading in main.StyleDefinitionsPart!.Styles!.Elements<Style>().Where(s => (s.StyleId?.Value ?? "").StartsWith("Heading")))
    {
        heading.StyleRunProperties ??= new StyleRunProperties();
        heading.StyleRunProperties.RunFonts = new RunFonts { Ascii="Times New Roman", HighAnsi="Times New Roman", EastAsia="SimHei", ComplexScript="Times New Roman" };
    }
    var styles = main.StyleDefinitionsPart.Styles;
    styles.Append(new Style(new StyleName { Val="Title" }, new BasedOn { Val="Normal" },
        new StyleParagraphProperties(new SpacingBetweenLines { Before="1000", After="480", Line="360", LineRule=LineSpacingRuleValues.Auto }, new Indentation { FirstLine="0" }, new Justification { Val=JustificationValues.Center }),
        new StyleRunProperties(new RunFonts { Ascii="Times New Roman", HighAnsi="Times New Roman", EastAsia="SimHei" },new Bold(),new FontSize { Val="44" })) { Type=StyleValues.Paragraph, StyleId="ReportTitle" });
    styles.Append(new Style(new StyleName { Val="Table Text" }, new BasedOn { Val="Normal" },
        new StyleParagraphProperties(new SpacingBetweenLines { Line="240", LineRule=LineSpacingRuleValues.Auto, After="80" }, new Indentation { FirstLine="0" }),
        new StyleRunProperties(new FontSize { Val="20" })) { Type=StyleValues.Paragraph, StyleId="TableText" });
    styles.Append(new Style(new StyleName { Val="Figure Caption" },new BasedOn { Val="Normal" },
        new StyleParagraphProperties(new KeepNext(),new SpacingBetweenLines { Line="276",LineRule=LineSpacingRuleValues.Auto,Before="160",After="160" },new Indentation { FirstLine="0" },new Justification { Val=JustificationValues.Center }),
        new StyleRunProperties(new FontSize { Val="21" })) { Type=StyleValues.Paragraph,StyleId="FigureCaption" });
    Paragraph P(string value,string style="Normal",bool center=false)
    {
        var pp = new ParagraphProperties(new ParagraphStyleId { Val=style });
        if(center) { pp.Append(new Indentation { FirstLine="0" }); pp.Append(new Justification { Val=JustificationValues.Center }); }
        return new Paragraph(pp,new Run(new Text(value) { Space=SpaceProcessingModeValues.Preserve }));
    }
    body.Append(P(root.GetProperty("title").GetString()!,"ReportTitle"));
    body.Append(P(root.GetProperty("subtitle").GetString()!,"Normal",true));
    foreach(var meta in root.GetProperty("cover").EnumerateArray()) body.Append(P(meta.GetString()!,"Normal",true));
    body.Append(new Paragraph(new Run(new Break { Type=BreakValues.Page })));
    body.Append(P("目录","Heading1"));
    var toc = new Paragraph(new ParagraphProperties(new Indentation { FirstLine="0" }),
        new Run(new FieldChar { FieldCharType=FieldCharValues.Begin }),
        new Run(new FieldCode(" TOC \\o \"1-3\" \\h \\z \\u ") { Space=SpaceProcessingModeValues.Preserve }),
        new Run(new FieldChar { FieldCharType=FieldCharValues.Separate }),
        new Run(new Text("在 Word/WPS 中更新目录：选中目录，更新整个目录。")),
        new Run(new FieldChar { FieldCharType=FieldCharValues.End }));
    body.Append(toc);
    body.Append(new Paragraph(new Run(new Break { Type=BreakValues.Page })));
    uint drawingId=1;
    foreach(var block in root.GetProperty("blocks").EnumerateArray())
    {
        var type=block.GetProperty("type").GetString();
        if(type=="heading") body.Append(P(block.GetProperty("text").GetString()!,"Heading"+block.GetProperty("level").GetInt32()));
        else if(type=="paragraph") body.Append(P(block.GetProperty("text").GetString()!));
        else if(type=="pageBreak") body.Append(new Paragraph(new Run(new Break { Type=BreakValues.Page })));
        else if(type=="table")
        {
            var headers=block.GetProperty("headers").EnumerateArray().Select(x=>x.GetString()!).ToArray();
            var rows=block.GetProperty("rows").EnumerateArray().Select(x=>x.EnumerateArray().Select(y=>y.ValueKind==JsonValueKind.String ? y.GetString()! : y.ToString()).ToArray()).ToArray();
            var table=TableSamples.CreateSimpleTable(body,headers,rows);
            var props=table.GetFirstChild<TableProperties>()!;
            props.GetFirstChild<TableWidth>()!.Width="8306";
            props.GetFirstChild<TableWidth>()!.Type=TableWidthUnitValues.Dxa;
            props.Append(new TableLayout { Type=TableLayoutValues.Fixed });
            var grid=table.GetFirstChild<TableGrid>()!;
            var widths=Enumerable.Repeat(8306/headers.Length,headers.Length).ToArray();
            if(block.TryGetProperty("widths",out var ws)) widths=ws.EnumerateArray().Select(x=>x.GetInt32()).ToArray();
            grid.RemoveAllChildren();foreach(var width in widths) grid.Append(new GridColumn { Width=width.ToString() });
            int rowIndex=0;
            foreach(var row in table.Elements<TableRow>())
            {
                row.PrependChild(new TableRowProperties(rowIndex==0 ? new TableHeader() : new CantSplit()));
                int col=0;
                foreach(var cell in row.Elements<TableCell>())
                {
                    cell.PrependChild(new TableCellProperties(new TableCellWidth { Width=widths[col++].ToString(), Type=TableWidthUnitValues.Dxa }));
                    foreach(var p in cell.Elements<Paragraph>()) p.ParagraphProperties=new ParagraphProperties(new ParagraphStyleId { Val="TableText" });
                }
                rowIndex++;
            }
        }
        else if(type=="image")
        {
            var image=Path.GetFullPath(Path.Combine(Path.GetDirectoryName(source)!,block.GetProperty("path").GetString()!));
            var width=block.GetProperty("width").GetInt32();
            var height=block.GetProperty("height").GetInt32();
            double scale=Math.Min(552.0/width,690.0/height);
            long cx=(long)(width*scale*9525),cy=(long)(height*scale*9525);
            var part=main.AddImagePart(ImagePartType.Png);
            using(var stream=File.OpenRead(image)) part.FeedData(stream);
            var rel=main.GetIdOfPart(part);
            var label=block.GetProperty("caption").GetString()!;
            var drawing=new Drawing(new DW.Inline(
                new DW.Extent { Cx=cx,Cy=cy },new DW.EffectExtent { LeftEdge=0,TopEdge=0,RightEdge=0,BottomEdge=0 },
                new DW.DocProperties { Id=drawingId++,Name=label,Description=label },
                new DW.NonVisualGraphicFrameDrawingProperties(new A.GraphicFrameLocks { NoChangeAspect=true }),
                new A.Graphic(new A.GraphicData(new PIC.Picture(
                    new PIC.NonVisualPictureProperties(new PIC.NonVisualDrawingProperties { Id=0U,Name=Path.GetFileName(image) },new PIC.NonVisualPictureDrawingProperties()),
                    new PIC.BlipFill(new A.Blip { Embed=rel },new A.Stretch(new A.FillRectangle())),
                    new PIC.ShapeProperties(new A.Transform2D(new A.Offset { X=0,Y=0 },new A.Extents { Cx=cx,Cy=cy }),new A.PresetGeometry(new A.AdjustValueList()) { Preset=A.ShapeTypeValues.Rectangle })
                )) { Uri="http://schemas.openxmlformats.org/drawingml/2006/picture" })
            ) { DistanceFromTop=0U,DistanceFromBottom=0U,DistanceFromLeft=0U,DistanceFromRight=0U });
            body.Append(new Paragraph(new ParagraphProperties(new KeepNext(),new Indentation { FirstLine="0" },new Justification { Val=JustificationValues.Center }),new Run(drawing)));
            body.Append(P(label,"FigureCaption"));
        }
    }
    body.Append(sect);
    var settings=main.DocumentSettingsPart ?? main.AddNewPart<DocumentSettingsPart>();
    settings.Settings ??= new Settings();
    settings.Settings.Append(new UpdateFieldsOnOpen { Val=true });
    main.Document.Save();styles.Save();settings.Settings.Save();
    doc.PackageProperties.Title=root.GetProperty("title").GetString();
    doc.PackageProperties.Creator="课程设计小组（身份待补充）";
    foreach (var unused in main.Parts.Where(x => x.OpenXmlPart is ImagePart && !main.Document.Descendants<A.Blip>().Any(b => b.Embed?.Value == x.RelationshipId)).ToList())
        main.DeletePart(unused.OpenXmlPart);
}
using(var repair=WordprocessingDocument.Open(target,true))
{
    void Reorder(OpenXmlElement parent,string[] order)
    {
        var priority=order.Select((x,i)=>(x,i)).ToDictionary(x=>x.x,x=>x.i);
        var children=parent.ChildElements.ToList();
        var sorted=children.OrderBy(x=>priority.GetValueOrDefault(x.LocalName,999)).ToList();
        parent.RemoveAllChildren();foreach(var child in sorted) parent.Append(child);
    }
    var rorder="rStyle rFonts b bCs i iCs caps smallCaps strike dstrike outline shadow emboss imprint noProof snapToGrid vanish webHidden color spacing w kern position sz szCs highlight u effect bdr shd fitText vertAlign rtl cs em lang eastAsianLayout specVanish oMath".Split(' ');
    var porder="pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers pBdr shd tabs suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange".Split(' ');
    var sorder="name aliases basedOn next link autoRedefine hidden uiPriority semiHidden unhideWhenUsed qFormat locked personal personalCompose personalReply rsid pPr rPr tblPr trPr tcPr".Split(' ');
    var sectorder="headerReference footerReference footnotePr endnotePr type pgSz pgMar paperSrc pgBorders lnNumType pgNumType cols formProt vAlign noEndnote titlePg textDirection bidi rtlGutter docGrid printerSettings sectPrChange".Split(' ');
    var parts=new List<OpenXmlPartRootElement> { repair.MainDocumentPart!.Document,repair.MainDocumentPart.StyleDefinitionsPart!.Styles! };
    parts.AddRange(repair.MainDocumentPart.HeaderParts.Select(x=>x.Header));
    parts.AddRange(repair.MainDocumentPart.FooterParts.Select(x=>x.Footer));
    foreach(var rootpart in parts)
    {
        foreach(var element in rootpart.Descendants().ToList())
        {
            if(element.LocalName=="rPr") Reorder(element,rorder);
            else if(element.LocalName=="pPr") Reorder(element,porder);
            else if(element.LocalName=="style") Reorder(element,sorder);
            else if(element.LocalName=="sectPr") Reorder(element,sectorder);
        }
        rootpart.Save();
    }
}
using(var check=WordprocessingDocument.Open(target,false))
{
    var errors=new OpenXmlValidator().Validate(check).ToList();
    foreach(var e in errors.Take(20)) Console.Error.WriteLine($"{e.Path?.XPath}: {e.Description}");
    Console.WriteLine($"Generated: {target}; SDK validation errors: {errors.Count}");
    if(errors.Count>0) Environment.ExitCode=2;
}
