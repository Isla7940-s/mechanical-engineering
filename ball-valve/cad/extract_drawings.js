// Runs the drawing code from ../index.html in Node and records every primitive
// (lines, polylines with arc bulges, circles, texts, dimensions, leaders) in
// model coordinates (mm, y up) instead of SVG. Output: drawings.json
//
// Usage: node extract_drawings.js
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const start = html.indexOf('const META=');
const end = html.indexOf('\nfunction fit(svg,g)');
if (start < 0 || end < 0) throw new Error('drawing code not found in index.html');
let code = html.slice(start, end);

// Replace the SVG path builder with one that keeps geometry: points + bulges.
const pbStart = code.indexOf('class PB{');
const pbEnd = code.indexOf("Z(){this.d+='Z';return this}}", pbStart) + "Z(){this.d+='Z';return this}}".length;
code = code.slice(0, pbStart) + `class PB{constructor(){this.pts=[];this.closed=false}
  M(x,y){this.pts.push([x+OX,y+OY,0]);return this}
  L(x,y){this.pts.push([x+OX,y+OY,0]);return this}
  A(r,x,y,ccw,large){const p=this.pts[this.pts.length-1],q=[x+OX,y+OY,0];
    const c=Math.hypot(q[0]-p[0],q[1]-p[1]);let th=2*Math.asin(Math.min(1,c/(2*r)));if(large)th=2*Math.PI-th;
    p[2]=Math.tan(th/4)*(ccw?1:-1);this.pts.push(q);return this}
  Z(){this.closed=true;return this}
  get d(){return this}}` + code.slice(pbEnd);

const harness = `
const NO_SHEET_TABLES=1;
const document=undefined, window=undefined;
${code}
const E=[];
function ln(x1,y1,x2,y2,c){E.push({t:'line',p:[[x1+OX,y1+OY],[x2+OX,y2+OY]],c:c||'v'});}
function circ(x,y,r,c){E.push({t:'circle',p:[x+OX,y+OY],r,c:c||'v'});}
function path(d,c){E.push({t:'poly',pts:d.pts.map(p=>p.slice()),closed:d.closed,c:c||'v'});}
function poly(pts,c){E.push({t:'poly',pts:pts.map(p=>[p[0]+OX,p[1]+OY,0]),closed:true,c:c||'v'});}
function pline(pts,c){E.push({t:'poly',pts:pts.map(p=>[p[0]+OX,p[1]+OY,0]),closed:false,c:c||'v'});}
function txt(x,y,s,c,anchor,rot){E.push({t:'text',p:[x+OX,y+OY],s:String(s),c:c||'dt',a:anchor||'middle',rot:rot?-rot:0});}
function dline(x1,y1,x2,y2,both){E.push({t:'dline',p:[[x1+OX,y1+OY],[x2+OX,y2+OY]],both:both!==false});}
function dimH(x1,y1,x2,y2,yd,s){if(!DIMS)return;E.push({t:'dim',k:'H',p1:[x1+OX,y1+OY],p2:[x2+OX,y2+OY],at:yd+OY,s});}
function dimV(x1,y1,x2,y2,xd,s){if(!DIMS)return;E.push({t:'dim',k:'V',p1:[x1+OX,y1+OY],p2:[x2+OX,y2+OY],at:xd+OX,s});}
function leader(x1,y1,x2,y2,s){if(!DIMS)return;E.push({t:'leader',p:[[x1+OX,y1+OY],[x2+OX,y2+OY]],s});}
const out={meta:META,info:INFO,drawings:{}};
for(const id of Object.keys(DRAW)){E.length=0;DRAW[id]();out.drawings[id]=E.slice();}
E.length=0;dAsm();out.drawings.assembly=E.slice();
return out;`;

const result = new Function(harness)();
fs.writeFileSync(path.join(__dirname, 'drawings.json'), JSON.stringify(result));
for (const [k, v] of Object.entries(result.drawings)) console.log(k.padEnd(10), v.length, 'entities');
