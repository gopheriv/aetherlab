"""Run the reviewed startup matrices against actual code in fresh processes."""
import pytest

from tools.accept_startup_stories import CASE_REQUIREMENTS, run_case


@pytest.mark.parametrize(('feature','case'),[(feature,case) for feature,cases in CASE_REQUIREMENTS.items() for case in cases])
def test_startup_story_case(feature, case, tmp_path):
    run_case(feature,case,tmp_path/'owned')
