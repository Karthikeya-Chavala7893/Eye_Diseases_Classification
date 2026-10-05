import os
import re
import subprocess

def parse_markdown_to_html(md_text):
    lines = md_text.split('\n')
    html_lines = []
    
    in_code_block = False
    code_lang = ""
    code_content = []
    
    in_table = False
    table_rows = []
    
    in_div = False
    div_content = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check for code blocks
        if line.startswith('```'):
            if not in_code_block:
                in_code_block = True
                code_lang = line[3:].strip()
                code_content = []
            else:
                in_code_block = False
                code_str = '\n'.join(code_content)
                # Escape html in code
                code_str = code_str.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                html_lines.append(f'<div class="code-container"><pre><code class="language-{code_lang}">{code_str}</code></pre></div>')
            i += 1
            continue
            
        if in_code_block:
            code_content.append(line)
            i += 1
            continue
            
        # Check for HTML div
        if '<div align="center">' in line:
            in_div = True
            div_content = []
            i += 1
            continue
        elif '</div>' in line and in_div:
            in_div = False
            div_inner = '\n'.join(div_content)
            # parse inner markdown
            div_inner = re.sub(r'# (.*?)\n', r'<h1>\1</h1>\n', div_inner)
            div_inner = re.sub(r'### (.*?)\n', r'<div class="subtitle">\1</div>\n', div_inner)
            div_inner = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', div_inner)
            div_inner = re.sub(r'\*(.*?)\*', r'<em>\1</em>', div_inner)
            # Parse badges: [![alt](img)](url)
            badge_pattern = r'\[!\[(.*?)\]\((.*?)\)\]\((.*?)\)'
            div_inner = re.sub(badge_pattern, r'<a href="\3" class="badge-link"><img src="\2" alt="\1" /></a>', div_inner)
            html_lines.append(f'<div class="hero-header">{div_inner}</div>')
            i += 1
            continue
            
        if in_div:
            div_content.append(line)
            i += 1
            continue
            
        # Check for table
        if line.strip().startswith('|') and line.strip().endswith('|'):
            if not in_table:
                in_table = True
                table_rows = []
            table_rows.append(line)
            i += 1
            continue
        else:
            if in_table:
                in_table = False
                # Process table
                html_table = render_table(table_rows)
                html_lines.append(html_table)
                table_rows = []
                
        # Empty lines
        if not line.strip():
            html_lines.append('')
            i += 1
            continue
            
        # Horizontal rules
        if line.strip() == '---':
            html_lines.append('<hr />')
            i += 1
            continue
            
        # Blockquotes
        if line.startswith('> '):
            quote_lines = []
            while i < len(lines) and lines[i].startswith('>'):
                q_line = lines[i][1:].strip()
                quote_lines.append(q_line)
                i += 1
            quote_text = '<br/>'.join(quote_lines)
            quote_text = format_inline(quote_text)
            html_lines.append(f'<blockquote class="alert-box">{quote_text}</blockquote>')
            continue
            
        # Headings
        if line.startswith('## '):
            h2_text = format_inline(line[3:].strip())
            html_lines.append(f'<h2 class="section-heading">{h2_text}</h2>')
            i += 1
            continue
            
        if line.startswith('### '):
            h3_text = format_inline(line[4:].strip())
            html_lines.append(f'<h3 class="subsection-heading">{h3_text}</h3>')
            i += 1
            continue
            
        if line.startswith('#### '):
            h4_text = format_inline(line[5:].strip())
            html_lines.append(f'<h4 class="sub-subsection-heading">{h4_text}</h4>')
            i += 1
            continue
            
        # Unordered list items
        if line.strip().startswith('- ') or line.strip().startswith('* '):
            indent_level = (len(line) - len(line.lstrip())) // 2
            item_text = format_inline(line.strip()[2:])
            html_lines.append(f'<li style="margin-left: {indent_level * 18}px;">{item_text}</li>')
            i += 1
            continue
            
        # Ordered list items
        match_ol = re.match(r'^(\d+)\.\s+(.*)', line.strip())
        if match_ol:
            num = match_ol.group(1)
            item_text = format_inline(match_ol.group(2))
            html_lines.append(f'<div class="numbered-item"><span class="num-badge">{num}</span><span class="num-text">{item_text}</span></div>')
            i += 1
            continue
            
        # Regular paragraph
        p_text = format_inline(line)
        html_lines.append(f'<p>{p_text}</p>')
        i += 1
        
    if in_table:
        html_table = render_table(table_rows)
        html_lines.append(html_table)
        
    return '\n'.join(html_lines)


def format_inline(text):
    # Bold with backticks
    text = re.sub(r'\*\*`([^`]+)`\*\*', r'<strong><code>\1</code></strong>', text)
    # Bold
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    # Inline code
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    # Italic
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    # Links
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    return text


def render_table(rows):
    if not rows:
        return ''
    
    html = ['<div class="table-responsive"><table class="custom-table">']
    
    # Header
    header_cols = [c.strip() for c in rows[0].strip('|').split('|')]
    html.append('<thead><tr>')
    for col in header_cols:
        html.append(f'<th>{format_inline(col)}</th>')
    html.append('</tr></thead>')
    
    # Body (skip row 1 which is separator ---|---)
    html.append('<tbody>')
    for row in rows[2:]:
        cols = [c.strip() for c in row.strip('|').split('|')]
        html.append('<tr>')
        for col in cols:
            html.append(f'<td>{format_inline(col)}</td>')
        html.append('</tr>')
    html.append('</tbody></table></div>')
    
    return '\n'.join(html)


def main():
    md_path = r"c:\Users\chkar\Desktop\Eye_Diseases_Classification\README.md"
    html_path = r"c:\Users\chkar\Desktop\Eye_Diseases_Classification\README.html"
    pdf_path = r"c:\Users\chkar\Desktop\Eye_Diseases_Classification\README.pdf"
    
    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
        
    body_html = parse_markdown_to_html(md_content)
    
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VisionAI Documentation</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  @page {{
    size: A4 portrait;
    margin: 14mm 14mm 14mm 14mm;
    @bottom-center {{
      content: "VisionAI Documentation • Page " counter(page);
      font-size: 8pt;
      color: #64748b;
      font-family: 'Plus Jakarta Sans', sans-serif;
    }}
  }}

  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }}

  body {{
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: #1e293b;
    background: #ffffff;
    font-size: 9.5pt;
    line-height: 1.55;
    padding: 0;
  }}

  /* Hero / Centered Header */
  .hero-header {{
    text-align: center;
    padding: 16px 20px 14px 20px;
    background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
    border-radius: 12px;
    color: #ffffff;
    margin-bottom: 16px;
    border: 1px solid #334155;
    page-break-inside: avoid;
  }}

  .hero-header h1 {{
    font-size: 20pt;
    font-weight: 800;
    color: #38bdf8;
    letter-spacing: -0.5px;
    margin-bottom: 4px;
  }}

  .hero-header .subtitle {{
    font-size: 11pt;
    font-weight: 600;
    color: #cbd5e1;
    margin-bottom: 12px;
  }}

  .hero-header .badge-link {{
    display: inline-block;
    margin: 2px 3px;
    text-decoration: none;
    vertical-align: middle;
  }}

  .hero-header img {{
    height: 22px;
    border-radius: 4px;
    vertical-align: middle;
  }}

  /* Headings */
  h2.section-heading {{
    font-size: 12.5pt;
    font-weight: 700;
    color: #0f172a;
    background: #f1f5f9;
    padding: 6px 12px;
    border-radius: 6px;
    border-left: 4px solid #0284c7;
    margin-top: 18px;
    margin-bottom: 8px;
    page-break-after: avoid;
    break-after: avoid;
  }}

  h3.subsection-heading {{
    font-size: 10.5pt;
    font-weight: 700;
    color: #1e293b;
    margin-top: 12px;
    margin-bottom: 6px;
    page-break-after: avoid;
    break-after: avoid;
  }}

  h4.sub-subsection-heading {{
    font-size: 9.5pt;
    font-weight: 600;
    color: #334155;
    margin-top: 8px;
    margin-bottom: 4px;
    page-break-after: avoid;
    break-after: avoid;
  }}

  p {{
    margin-bottom: 7px;
    color: #334155;
  }}

  hr {{
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 14px 0;
  }}

  /* Numbered Items & Lists */
  .numbered-item {{
    display: flex;
    align-items: flex-start;
    margin-bottom: 6px;
  }}

  .num-badge {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    background: #0284c7;
    color: #ffffff;
    font-size: 7.5pt;
    font-weight: 700;
    border-radius: 50%;
    margin-right: 8px;
    flex-shrink: 0;
    margin-top: 2px;
  }}

  .num-text {{
    flex: 1;
    color: #334155;
  }}

  li {{
    color: #334155;
    margin-bottom: 4px;
    margin-left: 18px;
  }}

  /* Tables */
  .table-responsive {{
    width: 100%;
    margin: 10px 0 14px 0;
    page-break-inside: avoid;
    break-inside: avoid;
  }}

  table.custom-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 8.2pt;
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    overflow: hidden;
  }}

  table.custom-table th {{
    background: #0f172a;
    color: #f8fafc;
    font-weight: 700;
    text-align: left;
    padding: 6px 10px;
    border: 1px solid #334155;
    letter-spacing: 0.2px;
  }}

  table.custom-table td {{
    padding: 5.5px 10px;
    border: 1px solid #e2e8f0;
    color: #334155;
    vertical-align: top;
  }}

  table.custom-table tbody tr:nth-child(even) {{
    background: #f8fafc;
  }}

  /* Code & Diagram Blocks */
  .code-container {{
    margin: 9px 0 12px 0;
    page-break-inside: avoid;
    break-inside: avoid;
  }}

  pre {{
    background: #0f172a;
    color: #e2e8f0;
    padding: 9px 12px;
    border-radius: 8px;
    border: 1px solid #1e293b;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 7.2pt;
    line-height: 1.22;
    overflow-x: hidden;
    white-space: pre;
    letter-spacing: -0.2px;
  }}

  code {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 8.2pt;
    background: #f1f5f9;
    color: #0369a1;
    padding: 1px 4px;
    border-radius: 4px;
    border: 1px solid #e2e8f0;
  }}

  pre code {{
    background: transparent;
    color: #38bdf8;
    padding: 0;
    border: none;
    font-size: 7.2pt;
  }}

  /* Blockquote Alert */
  .alert-box {{
    background: #f0fdf4;
    border-left: 4px solid #16a34a;
    padding: 9px 14px;
    border-radius: 6px;
    margin: 10px 0;
    color: #166534;
    font-size: 8.5pt;
    page-break-inside: avoid;
    border-top: 1px solid #bbf7d0;
    border-right: 1px solid #bbf7d0;
    border-bottom: 1px solid #bbf7d0;
  }}

  /* Links */
  a {{
    color: #0284c7;
    text-decoration: none;
    font-weight: 500;
  }}

  strong {{
    font-weight: 700;
    color: #0f172a;
  }}

  /* Footer Section */
  .footer-center {{
    text-align: center;
    margin-top: 20px;
    padding-top: 12px;
    border-top: 1px solid #cbd5e1;
    page-break-inside: avoid;
  }}
</style>
</head>
<body>
{body_html}
</body>
</html>
"""

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(full_html)
    print(f"Generated HTML at: {html_path}")
    
    # Run Chrome Headless to generate PDF
    chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    edge_exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    
    browser_exe = chrome_exe if os.path.exists(chrome_exe) else edge_exe
    
    cmd = [
        browser_exe,
        "--headless",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        f"file:///{html_path.replace('\\', '/')}"
    ]
    
    print("Converting HTML to PDF with headless browser...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and os.path.exists(pdf_path):
        print(f"SUCCESS: PDF generated at: {pdf_path} (Size: {os.path.getsize(pdf_path)} bytes)")
    else:
        print(f"Browser output: {res.stdout}, stderr: {res.stderr}")

if __name__ == '__main__':
    main()
