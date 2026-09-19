import test from 'node:test';
import assert from 'node:assert/strict';
import {sampleAt,clock,beatScale} from '../dist/core.js';
test('gaps never extrapolate past 30 seconds or borrow future samples',()=>{const samples=[{t:10,bpm:120},{t:80,bpm:145}];assert.equal(sampleAt(samples,9),null);assert.equal(sampleAt(samples,40).bpm,120);assert.equal(sampleAt(samples,41),null);assert.equal(sampleAt(samples,80).bpm,145);});
test('paused, reduced, and missing signals have no pulse',()=>{assert.equal(beatScale(120,1,false),1);assert.equal(beatScale(undefined,1,true),1);assert.equal(beatScale(0,1,true),1);});
test('pulse rate follows BPM independently of playback speed',()=>{assert.ok(beatScale(120,.06,true)>1.04);assert.ok(Math.abs(beatScale(120,.06,true)-beatScale(120,.56,true))<1e-9);assert.ok(Math.abs(beatScale(60,.12,true)-beatScale(120,.06,true))<1e-9);});
test('playhead formats elapsed time without date wrapping',()=>{assert.equal(clock(7265),'121:05');assert.equal(clock(-1),'00:00');});
