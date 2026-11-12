"""Prompt helpers for the VLM scripts: chart_prompt / extract_csv / expected_header (reads vlm_eval/prompts.md)."""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
CHARTS = ["pie", "bar", "scatter", "line", "heatmap", "linexy"]
WORDS = {"pie": "pie", "bar": "bar", "scatter": "scatter", "line": "line", "heatmap": "heatmap", "linexy": "linexy"}
BUILTIN = {"linexy": """These images are frames from a video of one line chart seen in a VR headset while walking around it.
Read the chart and write its complete data table as CSV.
- Series: the name of each line, exactly as written in the legend.
- X: the x-axis value of each point, as printed on the x-axis (numbers only).
- Y: the y-axis value of each point, read carefully against the y-axis scale and gridlines (numbers only, no units).
Write one row per point, for every line and every point, in this exact format with this header:
Series,X,Y
Output only the CSV."""}

def chart_prompt(chart):
    text = open(os.path.join(HERE, "prompts.md"), encoding="utf-8").read()
    parts = re.split(r"^(#{1,4} .*)$", text, flags=re.M)          # [pre, head1, body1, head2, body2, ...]
    heads = [(parts[i], parts[i + 1]) for i in range(1, len(parts) - 1, 2)]
    pick = [b for h, b in heads if f"`{chart}`" in h] or \
           [b for h, b in heads if re.search(r"\b" + WORDS[chart] + r"\b", h, re.I)]
    for body in pick:
        m = re.search(r"```[a-z]*\s*\n(.*?)```", body, re.S)
        if m:
            return m.group(1).strip()
    if chart in BUILTIN:
        return BUILTIN[chart]
    sys.exit(f"No prompt for '{chart}' in vlm_eval/prompts.md")

def extract_csv(answer, header):
    text = re.sub(r"<think>.*?</think>", "", answer, flags=re.S)
    m = re.search(r"```(?:csv)?\s*\n(.*?)```", text, re.S)
    text = m.group(1) if m else text
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    norm = lambda l: l.replace(" ", "").lower()
    start = next((i for i, l in enumerate(lines) if norm(l) == norm(header)), None)
    if start is None:
        return "\n".join(lines) + "\n"
    out = [header]
    for l in lines[start + 1:]:
        if l.count(",") != header.count(","):
            break
        out.append(l)
    return "\n".join(out) + "\n"

def expected_header(prompt):
    hs = [l.strip() for l in prompt.splitlines() if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(,[A-Za-z_][A-Za-z0-9_]*)+", l.strip())]
    return hs[-1]

if __name__ == "__main__":
    for c in CHARTS:
        p = chart_prompt(c)
        print(f"{c:8} header: {expected_header(p)}")
