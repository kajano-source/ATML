"""ATML compiler tests (unittest, stdlib only)."""
import json
import os
import re
import unittest

from compiler.atmlc import compile_atml

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = os.path.join(HERE, "..", "examples")


def get_payload(html):
    m = re.search(r"window\.__ATML__\s*=\s*(\{.*?\});</script>", html, re.S)
    assert m, "no window.__ATML__ payload found"
    return json.loads(m.group(1))


class TestCompiler(unittest.TestCase):
    def test_passthrough_html(self):
        src = "<!DOCTYPE html><html><head><title>T</title></head><body><p>Hi</p></body></html>"
        out = compile_atml(src, filename="t.atml")
        self.assertIn("<p>Hi</p>", out)
        self.assertIn("compiled with ATML v1.0", out)

    def test_actor_svg_emit(self):
        src = ('<atml><stage id="s"><scene id="c">'
               '<actor id="a1" x="10" y="20" w="50" h="60" shape="rect" fill="#ff0000"/>'
               "</scene></stage></atml>")
        out = compile_atml(src, filename="t.atml")
        self.assertIn('data-atml-id="a1"', out)
        self.assertIn("<svg", out)
        self.assertIn("<rect", out)

    def test_keyframes_emit(self):
        src = ('<atml><stage id="s"><scene id="c">'
               '<actor id="a1" x="0" y="0" w="10" h="10"/>'
               '<animate target="a1" dur="2s"><key at="0%" opacity="0"/>'
               '<key at="100%" opacity="1"/></animate>'
               "</scene></stage></atml>")
        out = compile_atml(src, filename="t.atml")
        self.assertIn("@keyframes", out)

    def test_fps_json(self):
        src = ('<atml fps="24"><stage id="s"><scene id="c">'
               '<actor id="a1" x="0" y="0" w="10" h="10"/>'
               '<animate target="a1" dur="1s" fps="12">'
               '<key at="0%" x="0"/><key at="100%" x="10"/></animate>'
               "</scene></stage></atml>")
        out = compile_atml(src, filename="t.atml")
        data = get_payload(out)
        anims = list(data["animations"].values())
        self.assertTrue(any(str(a.get("fps")) == "12" for a in anims))

    def test_morph(self):
        src = ('<atml><stage id="s"><scene id="c">'
               '<actor id="m" x="0" y="0" w="100" h="100">'
               '<draw d="M0 0 L10 10" morph="M0 0 L20 20"/></actor>'
               '<animate target="m" dur="1s"><key at="0%" d="M0 0 L10 10"/>'
               '<key at="100%" d="M0 0 L20 20"/></animate>'
               "</scene></stage></atml>")
        out = compile_atml(src, filename="t.atml")
        self.assertIn("data-morph", out)

    def test_sugar_attrs(self):
        src = ('<html><body><h1 id="h" a-fade="" a-dur="1s">Hi</h1>'
               "</body></html>")
        out = compile_atml(src, filename="t.atml")
        self.assertIn("@keyframes", out)
        self.assertIn("atml-a-", out)

    def test_script_block_compiles(self):
        src = ('<atml><stage id="s"><scene id="c">'
               '<actor id="x" x="0" y="0" w="10" h="10"/>'
               '<script type="atml">actor Hero { x: 5; y: 6 }\n'
               "animate Spin -> { rotate: 360 } over 2s ease linear fps 60\n"
               "on click(#btn) -> play Spin\nfps 60;\n</script>"
               "</scene></stage></atml>")
        out = compile_atml(src, filename="t.atml")
        self.assertIn("ATML.defineActor", out)
        self.assertIn("Hero", out)
        self.assertIn("ATML.defineAnimation", out)

    def test_error_line_numbers(self):
        src = ("<atml>\n<stage id=\"s\">\n<scene id=\"c\">\n"
               "<actor id=\"a1\" x=\"0\" y=\"0\" w=\"10\" h=\"10\"/>\n"
               "<animate dur=\"2s\"><key at=\"0%\" x=\"0\"/></animate>\n"
               "</scene></stage></atml>")
        with self.assertRaises(ValueError) as ctx:
            compile_atml(src, filename="bad.atml")
        self.assertIn("bad.atml:5", str(ctx.exception))

    def test_bad_fps_error(self):
        src = ('<atml><stage id="s"><scene id="c">'
               '<actor id="a1" x="0" y="0" w="10" h="10"/>'
               '<animate target="a1" dur="1s" fps="0">'
               '<key at="0%" x="0"/></animate></scene></stage></atml>')
        with self.assertRaises(ValueError) as ctx:
            compile_atml(src, filename="f.atml")
        self.assertIn("f.atml:", str(ctx.exception))

    def test_all_examples_compile(self):
        for name in ("hello.atml", "dog.atml", "transitions.atml",
                     "fps.atml", "morph.atml", "site.atml"):
            path = os.path.join(EXAMPLES, name)
            with open(path, encoding="utf-8") as f:
                src = f.read()
            out = compile_atml(src, filename=name)
            self.assertIn("compiled with ATML v1.0", out, name)
            self.assertIn("window.__ATML__", out, name)

    def test_publish_single_page(self):
        import shutil
        import tempfile
        from compiler.atmlc import main as atml_main
        tmp = tempfile.mkdtemp(prefix="atml-pub-")
        try:
            src = os.path.join(tmp, "site.atml")
            with open(src, "w", encoding="utf-8") as f:
                f.write("<!DOCTYPE html><html><head><title>S</title></head>"
                        "<body><p>Hi</p></body></html>")
            outdir = os.path.join(tmp, "dist")
            rc = atml_main(["publish", src, "-o", outdir])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.isfile(os.path.join(outdir, "index.html")))
            self.assertTrue(os.path.isfile(os.path.join(outdir, ".nojekyll")))
            with open(os.path.join(outdir, "index.html"), encoding="utf-8") as f:
                self.assertIn("<p>Hi</p>", f.read())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_publish_multi_page_assets_sitemap(self):
        import shutil
        import tempfile
        from compiler.atmlc import main as atml_main
        tmp = tempfile.mkdtemp(prefix="atml-pub2-")
        try:
            os.makedirs(os.path.join(tmp, "assets"))
            with open(os.path.join(tmp, "assets", "logo.svg"), "w") as f:
                f.write("<svg></svg>")
            for name in ("index.atml", "about.atml"):
                with open(os.path.join(tmp, name), "w", encoding="utf-8") as f:
                    f.write('<!DOCTYPE html><html><head><title>%s</title></head>'
                            '<body><img src="assets/logo.svg"/></body></html>' % name)
            outdir = os.path.join(tmp, "dist")
            rc = atml_main(["publish", os.path.join(tmp, "index.atml"),
                            os.path.join(tmp, "about.atml"),
                            "-o", outdir, "--base", "/myrepo/"])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.isfile(os.path.join(outdir, "index.html")))
            self.assertTrue(os.path.isfile(os.path.join(outdir, "about.html")))
            self.assertTrue(os.path.isfile(
                os.path.join(outdir, "assets", "logo.svg")))
            self.assertTrue(os.path.isfile(os.path.join(outdir, "sitemap.xml")))
            with open(os.path.join(outdir, "index.html"), encoding="utf-8") as f:
                body = f.read()
            self.assertIn("/myrepo/assets/logo.svg", body)

            bad = os.path.join(tmp, "bad.atml")
            with open(bad, "w", encoding="utf-8") as f:
                f.write('<!DOCTYPE html><html><body>'
                        '<img src="assets/nope.png"/></body></html>')
            rc = atml_main(["publish", bad, "-o", os.path.join(tmp, "dist2")])
            self.assertEqual(rc, 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
