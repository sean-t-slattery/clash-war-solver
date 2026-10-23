"""Portable, self-contained attack reports. All user strings are escaped."""
import html
import json


def report(job):
    checkpoint = job["checkpoint"]
    leaders = checkpoint["leaders"]
    inputs = job["inputs"]
    layout = inputs["layout"]
    esc = lambda x: html.escape(str(x))
    parts = ["<!doctype html><html lang='en'><meta charset='utf-8'><title>Attack research report</title>",
             "<style>body{font:15px system-ui;max-width:1100px;margin:40px auto;padding:20px;color:#172b31}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}svg{width:100%;max-height:550px;background:#eff5f0}.notice{background:#fff0ca;padding:16px}pre{white-space:pre-wrap}@media print{button{display:none}}</style>",
             f"<h1>{esc(layout['name'])}</h1><p class='notice'>Approximate research simulator. Synthetic or uncalibrated parameters are not live game facts. Monte Carlo success rates are not real-world attack probabilities.</p>",
             f"<p>Job {esc(job['id'])} · {esc(job['status'])} · {job['active_seconds']:.1f} active seconds · {checkpoint['simulations']} simulations</p>",
             "<button onclick='window.print()'>Print / save as PDF</button>"]
    for index, entry in enumerate(leaders):
        strategy = entry["strategy"]
        parts.append(f"<h2>{index+1}. {esc(strategy['name'])}</h2>")
        metrics = entry.get("validation")
        parts.append("<p>Independent finalist evaluation: "+(f"{metrics['successes']}/{metrics['samples']} simulated three-star outcomes" if metrics else "incomplete within budget")+". Winner ranked on search scenarios.</p>")
        parts.append("<svg viewBox='-4 -4 52 52' role='img' aria-label='Deployment map'>")
        for s in layout["structures"]:
            color = "#a6b5aa" if s["type"] == "wall" else "#dfaa50" if s["type"] == "town_hall" else "#53837b"
            parts.append(f"<rect x='{s['x']}' y='{s['y']}' width='{s['width']}' height='{s['height']}' fill='{color}' stroke='white' stroke-width='.12'><title>{esc(s['type'])}</title></rect>")
        for n, action in enumerate(sorted(strategy["actions"], key=lambda a: a["time"])):
            parts.append(f"<circle cx='{action['x']}' cy='{action['y']}' r='.8' fill='#233847'/><text x='{action['x']}' y='{action['y']+.35}' text-anchor='middle' fill='white' font-size='1'>{n+1}</text>")
        parts.append("</svg><table><tr><th>Time</th><th>Action</th><th>Quantity</th><th>Tile</th><th>Purpose</th><th>Tolerance</th></tr>")
        for action in sorted(strategy["actions"], key=lambda a: a["time"]):
            parts.append(f"<tr><td>{action['time']:.1f}s</td><td>{esc(action['kind'])} {esc(action['unit'])}</td><td>{action['quantity']}</td><td>({action['x']:.1f}, {action['y']:.1f})</td><td>{esc(action['purpose'])}</td><td>{esc(action['tolerance'])}</td></tr>")
        parts.append("</table><details><summary>Search and independent model statistics</summary><pre>"+esc(json.dumps({"search": entry["search"], "validation": metrics}, indent=2))+"</pre></details>")
    parts.append("<h2>Recorded assumptions</h2><pre>"+esc(json.dumps(inputs["request"]["uncertainty"], indent=2))+"</pre>")
    parts.append("<p>Coordinates use grid tiles, origin at the top of the isometric map. Negative or ≥44 positions are deployment-border coordinates. Timing and coordinate tolerances are assumed perturbation settings, not measured human tolerances.</p>")
    parts.append("<p>Pack: "+esc(inputs["pack"]["label"])+". No empirical calibration has been applied. Pets, equipment, siege behavior and advanced game mechanics are unsupported.</p>")
    parts.append("<footer>This material is unofficial and is not endorsed by Supercell. <a href='https://supercell.com/en/fan-content-policy/'>Fan Content Policy</a>.</footer></html>")
    return "".join(parts)
