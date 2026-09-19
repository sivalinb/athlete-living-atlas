export const SCENES = ['heart','trail','recovery','agents'];
export function sampleAt(samples, second, maxAge=30) {
  let chosen=null;
  for (const sample of samples) { if(sample.t>second) break; chosen=sample; }
  return chosen && second-chosen.t<=maxAge ? chosen : null;
}
export function clock(seconds) { const s=Math.max(0,Math.floor(seconds||0));return `${Math.floor(s/60).toString().padStart(2,'0')}:${(s%60).toString().padStart(2,'0')}`; }
export function beatScale(bpm, time, enabled) {
  if(!enabled || !Number.isFinite(bpm) || bpm<=0) return 1;
  const p=((time*bpm/60)%1);return 1+.045*Math.exp(-(((p-.12)/.07)**2))+.019*Math.exp(-(((p-.32)/.08)**2));
}
