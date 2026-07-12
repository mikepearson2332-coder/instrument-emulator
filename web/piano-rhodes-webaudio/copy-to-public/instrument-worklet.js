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

let wasm_bindgen = (function(exports) {
    let script_src;
    if (typeof document !== 'undefined' && document.currentScript !== null) {
        script_src = new URL(document.currentScript.src, location.href).toString();
    }

    class Synth {
        __destroy_into_raw() {
            const ptr = this.__wbg_ptr;
            this.__wbg_ptr = 0;
            SynthFinalization.unregister(this);
            return ptr;
        }
        free() {
            const ptr = this.__destroy_into_raw();
            wasm.__wbg_synth_free(ptr, 0);
        }
        /**
         * Number of currently sounding voices (for a CPU/voice meter).
         * @returns {number}
         */
        get active_voices() {
            const ret = wasm.synth_active_voices(this.__wbg_ptr);
            return ret >>> 0;
        }
        /**
         * Release everything (panic button / instrument switch).
         */
        all_notes_off() {
            wasm.synth_all_notes_off(this.__wbg_ptr);
        }
        /**
         * Build a synth for one instrument.
         *
         * - `params_json`: the contents of an `instruments/<name>/params/*.json`
         *   table (e.g. piano `grand.json`, rhodes `mk1.json`).
         * - `sample_rate`: pass the live `AudioContext.sampleRate` so there is no
         *   resampling and no pitch error (Android WebViews usually run 48000).
         * - `seed`: PRNG seed for the stochastic parts (noise/phase); any value.
         * @param {string} params_json
         * @param {number} sample_rate
         * @param {bigint} seed
         */
        constructor(params_json, sample_rate, seed) {
            const ptr0 = passStringToWasm0(params_json, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
            const len0 = WASM_VECTOR_LEN;
            const ret = wasm.synth_new(ptr0, len0, sample_rate, seed);
            if (ret[2]) {
                throw takeFromExternrefTable0(ret[1]);
            }
            this.__wbg_ptr = ret[0];
            SynthFinalization.register(this, this.__wbg_ptr, this);
            return this;
        }
        /**
         * Release a note (respects the sustain pedal, like the native engine).
         * @param {number} midi
         */
        note_off(midi) {
            wasm.synth_note_off(this.__wbg_ptr, midi);
        }
        /**
         * Start a note. `velocity` is MIDI-style 1..=127.
         * @param {number} midi
         * @param {number} velocity
         */
        note_on(midi, velocity) {
            wasm.synth_note_on(this.__wbg_ptr, midi, velocity);
        }
        /**
         * Render `out.len()` mono frames, overwriting `out`. Call once per audio
         * block with the worklet's output Float32Array. Dead voices are culled.
         * @param {Float32Array} out
         */
        render(out) {
            var ptr0 = passArrayF32ToWasm0(out, wasm.__wbindgen_malloc);
            var len0 = WASM_VECTOR_LEN;
            wasm.synth_render(this.__wbg_ptr, ptr0, len0, out);
        }
        /**
         * Sustain pedal down/up.
         * @param {boolean} down
         */
        set_pedal(down) {
            wasm.synth_set_pedal(this.__wbg_ptr, down);
        }
    }
    if (Symbol.dispose) Synth.prototype[Symbol.dispose] = Synth.prototype.free;
    exports.Synth = Synth;

    function start() {
        wasm.start();
    }
    exports.start = start;
    function __wbg_get_imports() {
        const import0 = {
            __proto__: null,
            __wbg_Error_92b29b0548f8b746: function(arg0, arg1) {
                const ret = Error(getStringFromWasm0(arg0, arg1));
                return ret;
            },
            __wbg___wbindgen_copy_to_typed_array_4db0cbe2cc60dbee: function(arg0, arg1, arg2) {
                new Uint8Array(arg2.buffer, arg2.byteOffset, arg2.byteLength).set(getArrayU8FromWasm0(arg0, arg1));
            },
            __wbg___wbindgen_throw_344f42d3211c4765: function(arg0, arg1) {
                throw new Error(getStringFromWasm0(arg0, arg1));
            },
            __wbg_error_a6fa202b58aa1cd3: function(arg0, arg1) {
                let deferred0_0;
                let deferred0_1;
                try {
                    deferred0_0 = arg0;
                    deferred0_1 = arg1;
                    console.error(getStringFromWasm0(arg0, arg1));
                } finally {
                    wasm.__wbindgen_free(deferred0_0, deferred0_1, 1);
                }
            },
            __wbg_new_227d7c05414eb861: function() {
                const ret = new Error();
                return ret;
            },
            __wbg_stack_3b0d974bbf31e44f: function(arg0, arg1) {
                const ret = arg1.stack;
                const ptr1 = passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
                const len1 = WASM_VECTOR_LEN;
                getDataViewMemory0().setInt32(arg0 + 4 * 1, len1, true);
                getDataViewMemory0().setInt32(arg0 + 4 * 0, ptr1, true);
            },
            __wbindgen_init_externref_table: function() {
                const table = wasm.__wbindgen_externrefs;
                const offset = table.grow(4);
                table.set(0, undefined);
                table.set(offset + 0, undefined);
                table.set(offset + 1, null);
                table.set(offset + 2, true);
                table.set(offset + 3, false);
            },
        };
        return {
            __proto__: null,
            "./instrument_wasm_bg.js": import0,
        };
    }

    const SynthFinalization = (typeof FinalizationRegistry === 'undefined')
        ? { register: () => {}, unregister: () => {} }
        : new FinalizationRegistry(ptr => wasm.__wbg_synth_free(ptr, 1));

    function getArrayU8FromWasm0(ptr, len) {
        ptr = ptr >>> 0;
        return getUint8ArrayMemory0().subarray(ptr / 1, ptr / 1 + len);
    }

    let cachedDataViewMemory0 = null;
    function getDataViewMemory0() {
        if (cachedDataViewMemory0 === null || cachedDataViewMemory0.buffer.detached === true || (cachedDataViewMemory0.buffer.detached === undefined && cachedDataViewMemory0.buffer !== wasm.memory.buffer)) {
            cachedDataViewMemory0 = new DataView(wasm.memory.buffer);
        }
        return cachedDataViewMemory0;
    }

    let cachedFloat32ArrayMemory0 = null;
    function getFloat32ArrayMemory0() {
        if (cachedFloat32ArrayMemory0 === null || cachedFloat32ArrayMemory0.byteLength === 0) {
            cachedFloat32ArrayMemory0 = new Float32Array(wasm.memory.buffer);
        }
        return cachedFloat32ArrayMemory0;
    }

    function getStringFromWasm0(ptr, len) {
        return decodeText(ptr >>> 0, len);
    }

    let cachedUint8ArrayMemory0 = null;
    function getUint8ArrayMemory0() {
        if (cachedUint8ArrayMemory0 === null || cachedUint8ArrayMemory0.byteLength === 0) {
            cachedUint8ArrayMemory0 = new Uint8Array(wasm.memory.buffer);
        }
        return cachedUint8ArrayMemory0;
    }

    function passArrayF32ToWasm0(arg, malloc) {
        const ptr = malloc(arg.length * 4, 4) >>> 0;
        getFloat32ArrayMemory0().set(arg, ptr / 4);
        WASM_VECTOR_LEN = arg.length;
        return ptr;
    }

    function passStringToWasm0(arg, malloc, realloc) {
        if (realloc === undefined) {
            const buf = cachedTextEncoder.encode(arg);
            const ptr = malloc(buf.length, 1) >>> 0;
            getUint8ArrayMemory0().subarray(ptr, ptr + buf.length).set(buf);
            WASM_VECTOR_LEN = buf.length;
            return ptr;
        }

        let len = arg.length;
        let ptr = malloc(len, 1) >>> 0;

        const mem = getUint8ArrayMemory0();

        let offset = 0;

        for (; offset < len; offset++) {
            const code = arg.charCodeAt(offset);
            if (code > 0x7F) break;
            mem[ptr + offset] = code;
        }
        if (offset !== len) {
            if (offset !== 0) {
                arg = arg.slice(offset);
            }
            ptr = realloc(ptr, len, len = offset + arg.length * 3, 1) >>> 0;
            const view = getUint8ArrayMemory0().subarray(ptr + offset, ptr + len);
            const ret = cachedTextEncoder.encodeInto(arg, view);

            offset += ret.written;
            ptr = realloc(ptr, len, offset, 1) >>> 0;
        }

        WASM_VECTOR_LEN = offset;
        return ptr;
    }

    function takeFromExternrefTable0(idx) {
        const value = wasm.__wbindgen_externrefs.get(idx);
        wasm.__externref_table_dealloc(idx);
        return value;
    }

    let cachedTextDecoder = new TextDecoder('utf-8', { ignoreBOM: true, fatal: true });
    cachedTextDecoder.decode();
    function decodeText(ptr, len) {
        return cachedTextDecoder.decode(getUint8ArrayMemory0().subarray(ptr, ptr + len));
    }

    const cachedTextEncoder = new TextEncoder();

    if (!('encodeInto' in cachedTextEncoder)) {
        cachedTextEncoder.encodeInto = function (arg, view) {
            const buf = cachedTextEncoder.encode(arg);
            view.set(buf);
            return {
                read: arg.length,
                written: buf.length
            };
        };
    }

    let WASM_VECTOR_LEN = 0;

    let wasmModule, wasmInstance, wasm;
    function __wbg_finalize_init(instance, module) {
        wasmInstance = instance;
        wasm = instance.exports;
        wasmModule = module;
        cachedDataViewMemory0 = null;
        cachedFloat32ArrayMemory0 = null;
        cachedUint8ArrayMemory0 = null;
        wasm.__wbindgen_start();
        return wasm;
    }

    async function __wbg_load(module, imports) {
        if (typeof Response === 'function' && module instanceof Response) {
            if (typeof WebAssembly.instantiateStreaming === 'function') {
                try {
                    return await WebAssembly.instantiateStreaming(module, imports);
                } catch (e) {
                    const validResponse = module.ok && expectedResponseType(module.type);

                    if (validResponse && module.headers.get('Content-Type') !== 'application/wasm') {
                        console.warn("`WebAssembly.instantiateStreaming` failed because your server does not serve Wasm with `application/wasm` MIME type. Falling back to `WebAssembly.instantiate` which is slower. Original error:\n", e);

                    } else { throw e; }
                }
            }

            const bytes = await module.arrayBuffer();
            return await WebAssembly.instantiate(bytes, imports);
        } else {
            const instance = await WebAssembly.instantiate(module, imports);

            if (instance instanceof WebAssembly.Instance) {
                return { instance, module };
            } else {
                return instance;
            }
        }

        function expectedResponseType(type) {
            switch (type) {
                case 'basic': case 'cors': case 'default': return true;
            }
            return false;
        }
    }

    function initSync(module) {
        if (wasm !== undefined) return wasm;


        if (module !== undefined) {
            if (Object.getPrototypeOf(module) === Object.prototype) {
                ({module} = module)
            } else {
                console.warn('using deprecated parameters for `initSync()`; pass a single object instead')
            }
        }

        const imports = __wbg_get_imports();
        if (!(module instanceof WebAssembly.Module)) {
            module = new WebAssembly.Module(module);
        }
        const instance = new WebAssembly.Instance(module, imports);
        return __wbg_finalize_init(instance, module);
    }

    async function __wbg_init(module_or_path) {
        if (wasm !== undefined) return wasm;


        if (module_or_path !== undefined) {
            if (Object.getPrototypeOf(module_or_path) === Object.prototype) {
                ({module_or_path} = module_or_path)
            } else {
                console.warn('using deprecated parameters for the initialization function; pass a single object instead')
            }
        }

        if (module_or_path === undefined && script_src !== undefined) {
            module_or_path = script_src.replace(/\.js$/, "_bg.wasm");
        }
        const imports = __wbg_get_imports();

        if (typeof module_or_path === 'string' || (typeof Request === 'function' && module_or_path instanceof Request) || (typeof URL === 'function' && module_or_path instanceof URL)) {
            module_or_path = fetch(module_or_path);
        }

        const { instance, module } = await __wbg_load(await module_or_path, imports);

        return __wbg_finalize_init(instance, module);
    }

    return Object.assign(__wbg_init, { initSync }, exports);
})({ __proto__: null });

// AudioWorkletProcessor body. build_wasm.ps1 concatenates this AFTER the
// wasm-bindgen `--target no-modules` glue to produce a single self-contained
// `instrument-worklet.js` (no imports), served untransformed from public/.
// The glue above defined a module-scope `wasm_bindgen`; pull the API off it.
//
// This file is not used directly â€” edit it here, then run build_wasm.ps1.

const { initSync, Synth } = wasm_bindgen;

class InstrumentProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const { module, paramsJson, seed } = options.processorOptions;
    // no-modules initSync also takes the { module } object form.
    initSync({ module });
    // seed is a Rust u64 -> JS BigInt at the boundary.
    // `sampleRate` is a global in AudioWorkletGlobalScope.
    this.synth = new Synth(paramsJson, sampleRate, BigInt(seed ?? 0));
    this.port.onmessage = (e) => this.handle(e.data);
  }

  handle(msg) {
    switch (msg.type) {
      case 'noteOn':  this.synth.note_on(msg.midi, msg.velocity); break;
      case 'noteOff': this.synth.note_off(msg.midi); break;
      case 'pedal':   this.synth.set_pedal(msg.down); break;
      case 'allOff':  this.synth.all_notes_off(); break;
    }
  }

  process(_inputs, outputs) {
    const out = outputs[0];
    if (out.length === 0) return true;
    // Engine is mono: render into channel 0, then mirror to the rest.
    this.synth.render(out[0]);
    for (let c = 1; c < out.length; c++) out[c].set(out[0]);
    return true; // keep the processor alive
  }
}

registerProcessor('instrument-processor', InstrumentProcessor);

