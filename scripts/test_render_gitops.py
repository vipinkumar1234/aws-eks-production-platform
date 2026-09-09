import unittest
import re
from pathlib import Path
from render_gitops import TOKENS, render, ROOT


class RenderTest(unittest.TestCase):
    def test_environments_are_isolated_and_complete(self):
        outputs = {name: {"value": "example"} for name in TOKENS.values()}
        outputs["ecr_repository_url"] = {"value": "123456789012.dkr.ecr.us-east-1.amazonaws.com/game"}
        image = outputs["ecr_repository_url"]["value"] + "@sha256:" + "a" * 64
        original = (ROOT / "gitops/argocd/bootstrap/namespace.yaml").read_bytes()
        for env in ("dev", "prod"):
            files = render(env, outputs, "https://github.com/test/platform.git", image)
            self.assertTrue(files)
            for content in files.values():
                self.assertNotIn("REPLACE_WITH_", content)
            bootstrap = files[Path("argocd/bootstrap/namespace.yaml")]
            self.assertIn(f"path: gitops/environments/{env}/apps/sample-app", bootstrap)
            self.assertIn(image, files[Path("apps/sample-app/deployment.yaml")])
            prefix = f"gitops/environments/{env}/"
            for content in files.values():
                for reference in re.findall(r"\$values/(\S+)", content):
                    self.assertTrue(reference.startswith(prefix))
                    self.assertIn(Path(reference[len(prefix):]), files)
        self.assertEqual(original, (ROOT / "gitops/argocd/bootstrap/namespace.yaml").read_bytes())

    def test_mutable_image_rejected(self):
        with self.assertRaises(ValueError):
            render("dev", {"ecr_repository_url": {"value": "example"}}, "https://github.com/test/platform.git", "example:latest")


if __name__ == "__main__":
    unittest.main()
