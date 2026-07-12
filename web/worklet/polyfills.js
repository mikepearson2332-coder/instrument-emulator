// Minimal UTF-8 TextEncoder/TextDecoder for AudioWorkletGlobalScope.
//
// wasm-bindgen instantiates TextEncoder/TextDecoder at load to marshal strings
// (here: the params-table JSON passed to Synth). AudioWorkletGlobalScope does
// not provide them, so without this the glue throws before registerProcessor
// runs. build_wasm.ps1 prepends this file to the worklet, before the glue.

if (typeof globalThis.TextEncoder === 'undefined') {
  globalThis.TextEncoder = class TextEncoder {
    encode(str) {
      const bytes = [];
      for (let i = 0; i < str.length; i++) {
        let c = str.charCodeAt(i);
        if (c < 0x80) {
          bytes.push(c);
        } else if (c < 0x800) {
          bytes.push(0xc0 | (c >> 6), 0x80 | (c & 0x3f));
        } else if (c >= 0xd800 && c <= 0xdbff) {
          const c2 = str.charCodeAt(++i);
          c = 0x10000 + ((c & 0x3ff) << 10) + (c2 & 0x3ff);
          bytes.push(
            0xf0 | (c >> 18),
            0x80 | ((c >> 12) & 0x3f),
            0x80 | ((c >> 6) & 0x3f),
            0x80 | (c & 0x3f),
          );
        } else {
          bytes.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 0x3f), 0x80 | (c & 0x3f));
        }
      }
      return new Uint8Array(bytes);
    }
    // wasm-bindgen fast-paths through encodeInto when present.
    encodeInto(str, dest) {
      const enc = this.encode(str);
      dest.set(enc.subarray(0, dest.length));
      return { read: str.length, written: Math.min(enc.length, dest.length) };
    }
  };
}

if (typeof globalThis.TextDecoder === 'undefined') {
  globalThis.TextDecoder = class TextDecoder {
    constructor() {} // ignore ('utf-8', {...}) args
    decode(buf) {
      if (!buf) return '';
      const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf.buffer || buf);
      let out = '';
      let i = 0;
      while (i < bytes.length) {
        let c = bytes[i++];
        if (c >= 0x80) {
          if (c < 0xe0) {
            c = ((c & 0x1f) << 6) | (bytes[i++] & 0x3f);
          } else if (c < 0xf0) {
            c = ((c & 0x0f) << 12) | ((bytes[i++] & 0x3f) << 6) | (bytes[i++] & 0x3f);
          } else {
            c =
              ((c & 0x07) << 18) |
              ((bytes[i++] & 0x3f) << 12) |
              ((bytes[i++] & 0x3f) << 6) |
              (bytes[i++] & 0x3f);
          }
        }
        if (c > 0xffff) {
          c -= 0x10000;
          out += String.fromCharCode(0xd800 + (c >> 10), 0xdc00 + (c & 0x3ff));
        } else {
          out += String.fromCharCode(c);
        }
      }
      return out;
    }
  };
}
