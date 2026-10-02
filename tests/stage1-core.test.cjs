const assert = require('node:assert/strict');
const C = require('../dist/stage1-core.js');
const blocks = [{uid:'a',start:30,end:35},{uid:'b',start:15,end:45},{uid:'c',start:30,end:35}];
assert.equal(C.duration(blocks),40);
assert.deepEqual(C.toSource(blocks,5),{index:1,uid:'b',time:15});
assert.equal(C.toSource(blocks,40).time,35);
assert.equal(C.toSource(blocks,41),null);
assert.equal(C.toMontage(blocks,2,31),36);
const words=[{text:'uno',start:30,end:31},{text:'dos',start:31,end:32}];
const virtual=C.virtualWords(words,blocks);
assert.deepEqual(virtual.map(w=>w.blockUid),['a','a','b','b','c','c']);
assert.equal(virtual[4].start,35);
assert.deepEqual(words,[{text:'uno',start:30,end:31},{text:'dos',start:31,end:32}]);
for (const invalid of [{start:-1,end:2},{start:2,end:2},{start:0,end:Infinity},{start:0,end:101}]) assert.throws(()=>C.validate([invalid],100));
assert.notEqual(C.validate([{uid:'same',start:1,end:2},{uid:'same',start:1,end:2}],10)[0].uid,C.validate([{uid:'same',start:1,end:2},{uid:'same',start:1,end:2}],10)[1].uid);
assert.throws(()=>C.merge(blocks,0));
assert.throws(()=>C.merge([{start:4,end:5},{start:2,end:4}],0));
assert.throws(()=>C.merge([{start:2,end:4},{start:5,end:7}],0));
assert.equal(C.merge([{uid:'x',start:2,end:4},{uid:'y',start:4,end:7}],0)[0].end,7);
for(const aspect of ['9:16','16:9','1:1']) for(const x of [0,.5,1]) {
  const crop=C.cropBox(1920,1080,aspect,x,1);
  assert.ok(crop.x>=0&&crop.y>=0&&crop.x+crop.width<=1920&&crop.y+crop.height<=1080);
}
console.log('Etapa 1: funciones puras verificadas.');
