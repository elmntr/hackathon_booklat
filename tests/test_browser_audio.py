"""Exercise the actual inline worklet with Node, without a microphone."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_worklet_resampling_and_flush():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is optional for the inline browser audio self-check')
    html = (Path(__file__).resolve().parents[1] / 'web/index.html').read_text()
    script = html.split('<script>')[1].split('</script>')[0]
    subprocess.run([node, '--check'], input=script, text=True, check=True, capture_output=True)
    worklet = script.split('const WORKLET = `')[1].split('`;')[0]
    harness = r'''
const vm = require('node:vm');
const assert = require('node:assert/strict');
const worklet = WORKLET_SOURCE;
for (const rate of [16000, 44100, 48000, 96000]) for (const frameSize of [1600, 4000]) {
  const messages = [];
  let Processor;
  const sandbox = {sampleRate:rate, Int16Array,
    AudioWorkletProcessor:class {constructor(){this.port={postMessage:v=>messages.push(v)};}},
    registerProcessor:(_,cls)=>{Processor=cls;}};
  vm.runInNewContext(worklet,sandbox);
  const processor = new Processor({processorOptions:{frameSize}});
  const count = rate + Math.round(rate*.1);
  for(let i=0;i<count;i+=128){
    const input = new Float32Array(Math.min(128,count-i)).fill(.5);
    processor.process([[input]]);
  }
  processor.port.onmessage({data:'flush'});
  assert.equal(messages.pop(),'flushed');
  const samples = messages.flatMap(x=>Array.from(new Int16Array(x)));
  assert.ok(Math.abs(samples.length - 17600)<=1, `rate ${rate}: ${samples.length}`);
  assert.ok(samples.every(x=>x===16384));
  assert.ok(messages.slice(0,-1).every(x=>x.byteLength===frameSize*2));
  assert.equal(processor.process([[new Float32Array(128)]]),false);
}
'''
    import json
    harness = harness.replace('WORKLET_SOURCE', json.dumps(worklet))
    subprocess.run([node, '-e', harness], check=True, capture_output=True, text=True)
