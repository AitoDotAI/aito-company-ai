// A deliberately small markdown renderer — headings, code blocks, lists,
// tables, inline code/bold/links, paragraphs. Enough for the Documents reader
// pane without pulling in a markdown dependency. Not a full
// CommonMark implementation; the documents we render use simple markdown.
import React from "react";

function inline(text, key) {
  // escape, then re-introduce a few inline spans. Order matters: code first.
  const nodes = [];
  let rest = text;
  let i = 0;
  const re = /`([^`]+)`|\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^)]+)\)/;
  let m;
  while ((m = re.exec(rest))) {
    if (m.index > 0) nodes.push(rest.slice(0, m.index));
    if (m[1] != null) nodes.push(<code key={`${key}-${i++}`}>{m[1]}</code>);
    else if (m[2] != null) nodes.push(<strong key={`${key}-${i++}`}>{m[2]}</strong>);
    else nodes.push(<a key={`${key}-${i++}`} href={m[4]} target="_blank" rel="noreferrer">{m[3]}</a>);
    rest = rest.slice(m.index + m[0].length);
  }
  if (rest) nodes.push(rest);
  return nodes;
}

export function Markdown({ text }) {
  const out = [];
  const lines = (text || "").split("\n");
  let i = 0, key = 0;
  while (i < lines.length) {
    const before = i;
    const line = lines[i];
    if (line.startsWith("```")) {
      const buf = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) buf.push(lines[i++]);
      i++;
      out.push(<pre key={key++}><code>{buf.join("\n")}</code></pre>);
    } else if (/^#{1,4}\s/.test(line)) {
      const level = line.match(/^#+/)[0].length;
      const H = `h${Math.min(level + 1, 5)}`;
      out.push(React.createElement(H, { key: key++ }, inline(line.replace(/^#+\s/, ""), key)));
      i++;
    } else if (line.startsWith("|") && lines[i + 1] && /^\|[-: |]+\|/.test(lines[i + 1])) {
      const head = line.split("|").slice(1, -1).map((s) => s.trim());
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        rows.push(lines[i].split("|").slice(1, -1).map((s) => s.trim()));
        i++;
      }
      out.push(
        <table key={key++}><thead><tr>{head.map((h, j) => <th key={j}>{inline(h, key + "h" + j)}</th>)}</tr></thead>
          <tbody>{rows.map((r, ri) => <tr key={ri}>{r.map((c, ci) => <td key={ci}>{inline(c, key + ri + "c" + ci)}</td>)}</tr>)}</tbody></table>
      );
      continue;
    } else if (/^[-*]\s/.test(line)) {
      const items = [];
      while (i < lines.length && /^[-*]\s/.test(lines[i])) {
        items.push(<li key={items.length}>{inline(lines[i].replace(/^[-*]\s/, ""), key + "li" + items.length)}</li>);
        i++;
      }
      out.push(<ul key={key++}>{items}</ul>);
      continue;
    } else if (line.trim() === "") {
      i++;
    } else {
      const buf = [line];
      i++;
      while (i < lines.length && lines[i].trim() !== "" && !/^(#{1,4}\s|```|[-*]\s|\|)/.test(lines[i])) buf.push(lines[i++]);
      out.push(<p key={key++}>{inline(buf.join(" "), key)}</p>);
    }
    // safety net: a branch that forgot to advance must never hard-freeze the
    // tab. The `continue` branches (table/list) advance internally and skip
    // this; every fall-through branch reaches it.
    if (i === before) i++;
  }
  return <div className="md">{out}</div>;
}
