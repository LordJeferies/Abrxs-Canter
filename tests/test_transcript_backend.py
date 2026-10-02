import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
import abraxas_local as m

class BackendRegressionTests(unittest.TestCase):
    def exercise(self, selected, mlx_fail=False, cpp_ready=False):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            calls=[]
            def run(args):
                calls.append(args)
                if args[0]=='mlx' and mlx_fail:raise RuntimeError('MLX falló')
                if args[0] in ('mlx','cpp'):(root/'MASTER_WORD_LEVEL.json').write_text('{}')
            backend={'selected':selected,'mlx_whisper':{'executable':'mlx','model':'local-model'},'whisper_cpp':{'executable':'cpp','model':'local-ggml','ready':cpp_ready}}
            with patch.object(m,'run_checked',side_effect=run),patch.object(m,'require_command',return_value='ffmpeg'),patch.object(m,'load_transcript',return_value=([],{})):
                result=m._ab_original_generate_transcript(root/'master.mp4',root,None,backend)
            self.assertEqual(result,root/'MASTER_WORD_LEVEL.json')
            return [call[0] for call in calls]
    def test_successful_mlx_does_not_raise_no_engine(self):
        self.assertEqual(self.exercise('mlx_whisper'),['ffmpeg','mlx'])
    def test_cpp_selected(self):
        self.assertEqual(self.exercise('whisper_cpp',cpp_ready=True),['ffmpeg','cpp'])
    def test_mlx_fallback_once(self):
        self.assertEqual(self.exercise('mlx_whisper',True,True),['ffmpeg','mlx','cpp'])
    def test_missing_backend_is_actionable(self):
        with self.assertRaisesRegex(RuntimeError,'No hay un motor'):
            self.exercise(None)
    def test_mlx_error_preserved_without_fallback(self):
        with self.assertRaisesRegex(RuntimeError,'MLX falló'):
            self.exercise('mlx_whisper',True,False)

if __name__=='__main__':unittest.main()
