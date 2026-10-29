// Reads source from stdin, prints {"ok":bool,"error":str}. Parses only; never executes.
const parser = require("@babel/parser");
let s = "";
process.stdin.on("data", (d) => (s += d)).on("end", () => {
  try {
    parser.parse(s, { sourceType: "module", plugins: ["jsx", "classProperties"] });
    console.log(JSON.stringify({ ok: true }));
  } catch (e) {
    console.log(JSON.stringify({ ok: false, error: e.message }));
  }
});
