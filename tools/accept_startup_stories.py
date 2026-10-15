"""Fresh-process acceptance of CLI routing, optional Qt, and Qwen opt-in."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE_REQUIREMENTS = {
    "F03": {
        "parse-no-smoke": {"optional_flag"},
        "parse-default": {"default_prompt"},
        "parse-unicode": {"exact_custom_prompt", "unicode_prompt"},
        "dispatch-default": {"default_prompt", "main_dispatch", "request_boundary", "return_code"},
        "dispatch-unicode": {"exact_custom_prompt", "unicode_prompt", "main_dispatch", "request_boundary"},
        "dispatch-empty": {"explicit_empty_prompt", "main_dispatch", "request_boundary"},
        "dispatch-whitespace": {"exact_custom_prompt", "main_dispatch", "request_boundary"},
        "unknown-flag": {"usage_error", "nonzero_exit", "no_gui"},
    },
    "F05": {
        "qt-available": {"available_guard"},
        "missing-qt-guard": {"missing_guard", "install_instruction", "exception_cause"},
        "broken-qt-guard": {"broken_runtime_diagnosis", "exception_cause"},
        "missing-qt-entrypoint": {"actual_entrypoint", "exit_2", "install_instruction", "no_traceback", "no_window"},
        "broken-qt-entrypoint": {"broken_runtime_diagnosis", "actual_entrypoint", "exit_2", "no_traceback", "no_window"},
    },
    "F09": {
        "qwen-missing": {"missing_fallback"},
        "qwen-invalid-json": {"corrupt_fallback", "unchanged_input"},
        "qwen-invalid-utf8": {"corrupt_fallback", "unchanged_input"},
        "qwen-list-root": {"invalid_shape_fallback", "unchanged_input"},
        "qwen-null-root": {"invalid_shape_fallback", "unchanged_input"},
        "qwen-empty-root": {"invalid_shape_fallback", "unchanged_input"},
        "qwen-read-refused": {"read_error_fallback", "unchanged_input"},
        "qwen-model-selection": {"model", "matching_provider", "base_url", "embedded_key", "source"},
        "qwen-provider-fallback": {"first_provider_fallback", "model", "base_url"},
        "qwen-provider-not-list": {"invalid_provider_container", "model"},
        "qwen-provider-empty": {"empty_provider_fallback", "model"},
        "qwen-provider-invalid-entries": {"invalid_provider_entries", "matching_provider"},
        "qwen-provider-no-url": {"missing_url", "model", "embedded_key"},
        "qwen-env-lookup": {"named_environment_key", "key_trim"},
        "qwen-embedded-key-wins": {"embedded_key", "key_precedence"},
        "qwen-blank-embedded-key": {"named_environment_key", "blank_key_fallback"},
        "qwen-invalid-embedded-key": {"named_environment_key", "invalid_key_fallback"},
        "qwen-invalid-env-container": {"named_environment_key", "invalid_env_container"},
        "qwen-default-env-key": {"default_key_name", "embedded_key"},
        "qwen-invalid-key-without-env": {"invalid_key_ignored"},
        "qwen-default-home": {"default_home_path", "source"},
        "qwen-opt-in-absent": {"no_implicit_credentials"},
        "qwen-opt-in-zero": {"no_implicit_credentials"},
        "qwen-opt-in-true": {"exact_opt_in"},
        "qwen-opt-in-one": {"explicit_opt_in", "model", "base_url", "embedded_key"},
        "qwen-app-precedence": {"higher_tier_preserved"},
        "qwen-invalid-model": {"invalid_model_ignored", "provider_tuple_rejected", "no_partial_credentials", "unchanged_input"},
        "qwen-invalid-model-list": {"invalid_model_ignored", "provider_tuple_rejected", "no_partial_credentials", "unchanged_input"},
        "qwen-invalid-model-number": {"invalid_model_ignored", "provider_tuple_rejected", "no_partial_credentials", "unchanged_input"},
        "qwen-invalid-model-blank": {"invalid_model_ignored", "unchanged_input"},
        "qwen-invalid-url": {"invalid_url_ignored", "provider_tuple_rejected", "no_partial_credentials", "unchanged_input"},
        "qwen-invalid-env-key": {"invalid_env_key_fallback", "unchanged_input"},
        "qwen-blank-env-key": {"invalid_env_key_fallback", "unchanged_input"},
    },
}
COMMON_SOURCES = {"tools/accept_startup_stories.py", "tools/feature_acceptance.py",
                  "tests/test_startup_story_contracts.py", "test_features.py",
                  "aetherlab/core/settings.py", "aetherlab/core/atomic_json.py"}
FEATURE_SOURCES = {
    "F03": COMMON_SOURCES | {"aetherlab/__main__.py", "aetherlab/core/models.py",
                             "aetherlab/core/console.py", "aetherlab/services/pipeline.py"},
    "F05": COMMON_SOURCES | {"aetherlab/__main__.py", "aetherlab/ui/qt_compat.py",
                             "aetherlab/ui/app.py", "aetherlab/core/console.py"},
    "F09": COMMON_SOURCES,
}
DETAILS = {
    "F03": "Complete prompt-routing contract: 8 fresh-process cases; exact default/Unicode/empty/whitespace request at the real smoke request boundary, exit propagation and usage errors. Controlled pipeline results; no claim of full solver/cloud acceptance",
    "F05": "Complete optional-Qt contract: 5 fresh-process cases; installed guard, missing/broken-package guards/causes and actual module entry-point failures for missing/broken Qt, exit 2 and no window/traceback",
    "F09": "Complete Qwen opt-in contract: 33 fresh-process cases; file/schema/encoding/read failures, provider/key/path resolution, exact opt-in, higher-tier precedence, whole-provider rejection for malformed model/URL, unchanged input and credential-free debug/file logs; owned credentials only",
}

CHILD = r'''
import importlib.abc,io,json,logging,os,runpy,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,sys.argv[1])
base=Path(sys.argv[2]); case=sys.argv[3]
home=base/'home'; home.mkdir()
Path.home=classmethod(lambda cls:home)
captured_logs=io.StringIO()
logging.getLogger().addHandler(logging.StreamHandler(captured_logs))
logging.getLogger().setLevel(logging.DEBUG)
if case in ('missing-qt-guard','broken-qt-guard','missing-qt-entrypoint','broken-qt-entrypoint'):
    class BlockQt(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if fullname=='aetherlab.ui.main_window':
                raise AssertionError('A window was imported before the Qt availability guard')
            if fullname=='PyQt6' or fullname.startswith('PyQt6.'):
                if case.startswith('broken-qt'): raise OSError('Owned Qt runtime DLL load failure')
                raise ModuleNotFoundError('Owned missing optional GUI package',name=fullname)
    sys.meta_path.insert(0,BlockQt())
if case.endswith('qt-entrypoint'):
    sys.argv=['aetherlab']
    runpy.run_module('aetherlab',run_name='__main__')
elif case in ('missing-qt-guard','broken-qt-guard'):
    from aetherlab.ui import qt_compat
    try: qt_compat.require_qt()
    except RuntimeError as error:
        assert 'PyQt6' in str(error) and 'pip install' in str(error)
        if case=='missing-qt-guard': assert isinstance(error.__cause__,ModuleNotFoundError)
        else:
            assert isinstance(error.__cause__,OSError)
            assert 'could not be loaded' in str(error) and 'is not installed' not in str(error)
        assert qt_compat.QtWidgets is None
    else: raise AssertionError('Missing Qt was not rejected')
elif case=='qt-available':
    from aetherlab.ui import qt_compat
    assert qt_compat.QT_IMPORT_ERROR is None
    assert qt_compat.require_qt() is None
    assert all(value is not None for value in (qt_compat.QtCore,qt_compat.QtGui,qt_compat.QtWidgets))
elif case.startswith('qwen-'):
    from aetherlab.core import settings
    path=base/'qwen.json'
    os.environ['QWEN_SETTINGS_PATH']=str(path)
    payload={'model':{'name':'owned-qwen-model'},'modelProviders':{'openai':[
        {'id':'other','baseUrl':'https://other.invalid/v1','envKey':'OWNED_QWEN_KEY'},
        {'id':'owned-qwen-model','baseUrl':'https://qwen.invalid/v1','envKey':'OWNED_QWEN_KEY'}]},
        'env':{'OWNED_QWEN_KEY':'owned-qwen-key'}}
    if case=='qwen-provider-fallback': payload['model']['name']='unmatched'
    elif case=='qwen-provider-not-list': payload['modelProviders']['openai']={}
    elif case=='qwen-provider-empty': payload['modelProviders']['openai']=[]
    elif case=='qwen-provider-invalid-entries': payload['modelProviders']['openai']=[None,'bad',42,payload['modelProviders']['openai'][1]]
    elif case=='qwen-provider-no-url': payload['modelProviders']['openai'][1].pop('baseUrl')
    elif case=='qwen-env-lookup':
        payload['env']={}; os.environ['OWNED_QWEN_KEY']='  owned-qwen-key  '
    elif case=='qwen-embedded-key-wins': os.environ['OWNED_QWEN_KEY']='other-owned-key'
    elif case in ('qwen-blank-embedded-key','qwen-invalid-embedded-key','qwen-invalid-env-container','qwen-invalid-key-without-env'):
        payload['env']={'OWNED_QWEN_KEY':'  ' if case=='qwen-blank-embedded-key' else 42}
        if case!='qwen-invalid-key-without-env': os.environ['OWNED_QWEN_KEY']='owned-qwen-key'
        if case=='qwen-invalid-env-container': payload['env']=[]
    elif case=='qwen-default-env-key':
        payload['modelProviders']['openai'][1].pop('envKey')
        payload['env']={'DASHSCOPE_API_KEY':'owned-qwen-key'}
    elif case.startswith('qwen-invalid-model'):
        payload['model']['name']={'qwen-invalid-model':{'unexpected':'object'},'qwen-invalid-model-list':[],
            'qwen-invalid-model-number':42,'qwen-invalid-model-blank':'   '}[case]
    elif case=='qwen-invalid-url': payload['modelProviders']['openai'][1]['baseUrl']={'unexpected':'object'}
    elif case in ('qwen-invalid-env-key','qwen-blank-env-key'):
        payload['modelProviders']['openai'][1]['envKey']=['unexpected'] if case=='qwen-invalid-env-key' else '  '
        payload['env']={'DASHSCOPE_API_KEY':'owned-qwen-key'}
    if case=='qwen-default-home':
        os.environ.pop('QWEN_SETTINGS_PATH')
        path=home/'.qwen'/'settings.json'; path.parent.mkdir()
    if case!='qwen-missing':
        if case=='qwen-invalid-json': path.write_text('{invalid',encoding='utf-8')
        elif case=='qwen-invalid-utf8': path.write_bytes(b'\xffinvalid')
        else: path.write_text(json.dumps([] if case=='qwen-list-root' else None if case=='qwen-null-root' else {} if case=='qwen-empty-root' else payload),encoding='utf-8')
    before=path.read_bytes() if path.exists() else None
    environment=dict(os.environ)
    if case.startswith('qwen-opt-in-') or case=='qwen-app-precedence':
        mode=case.removeprefix('qwen-opt-in-')
        if mode!='absent': os.environ['AETHERLAB_QWEN_AUTOLOAD']={'zero':'0','true':'true','one':'1'}.get(mode,'1')
        else: os.environ.pop('AETHERLAB_QWEN_AUTOLOAD',None)
        if case=='qwen-app-precedence':
            settings.save_app_config({'model':'app-model','api_key':'owned-app-key','base_url':'https://app.invalid/v1'})
        if mode in ('absent','zero','true'):
            def forbidden(): raise AssertionError('Qwen was read without explicit opt-in')
            settings.load_qwen_settings=forbidden
        value=settings.load_settings()
        if case=='qwen-app-precedence':
            good=(value.llm_model=='app-model' and value.openai_api_key=='owned-app-key' and value.openai_base_url=='https://app.invalid/v1')
        elif mode=='one':
            good=(value.llm_model=='owned-qwen-model' and value.openai_api_key=='owned-qwen-key' and value.openai_base_url=='https://qwen.invalid/v1')
        else: good=value.llm_model!='owned-qwen-model' and value.openai_api_key is None and value.openai_base_url is None
        assert good, 'Qwen opt-in/precedence contract was not respected'
    else:
        if case=='qwen-read-refused':
            from unittest.mock import patch
            original=Path.read_text
            def refuse(target,*args,**kwargs):
                if target==path: raise PermissionError('Owned Qwen read refusal')
                return original(target,*args,**kwargs)
            with patch.object(Path,'read_text',refuse): value=settings.load_qwen_settings(path)
        else: value=settings.load_qwen_settings(None if case=='qwen-default-home' else path)
        if case in ('qwen-missing','qwen-invalid-json','qwen-invalid-utf8','qwen-list-root','qwen-null-root','qwen-empty-root','qwen-read-refused'):
            assert value=={}, 'Invalid or unavailable Qwen file must be ignored'
        elif case.startswith('qwen-invalid-model') or case=='qwen-invalid-url':
            if case=='qwen-invalid-model-blank': assert 'model' not in value
            else:
                assert value=={}, 'Malformed provider was partially inherited'
                from unittest.mock import patch
                with patch.dict(os.environ,{'AETHERLAB_QWEN_AUTOLOAD':'1'}):
                    loaded=settings.load_settings()
                neutral=(loaded.openai_api_key is None and loaded.openai_base_url is None
                         and loaded.llm_model!='owned-qwen-model')
                assert neutral, 'Malformed provider credentials reached fallback settings'
        elif case in ('qwen-invalid-env-key','qwen-blank-env-key'):
            good=value.get('api_key')=='owned-qwen-key'
            assert good, 'Invalid envKey did not use the default key name'
        elif case in ('qwen-provider-not-list','qwen-provider-empty'):
            assert value['model']=='owned-qwen-model' and 'base_url' not in value and 'api_key' not in value
        elif case=='qwen-provider-no-url':
            good=value.get('api_key')=='owned-qwen-key'
            assert good and 'base_url' not in value
        elif case=='qwen-invalid-key-without-env': assert 'api_key' not in value
        else:
            assert value['model']==('unmatched' if case=='qwen-provider-fallback' else 'owned-qwen-model')
            assert value['base_url']==('https://other.invalid/v1' if case=='qwen-provider-fallback' else 'https://qwen.invalid/v1')
            good=value.get('api_key')=='owned-qwen-key'
            assert good, 'Expected owned Qwen key was not resolved'
            assert value['source']==str(path)
        assert dict(os.environ)==environment, 'Qwen reader mutated the process environment'
    assert (path.read_bytes() if path.exists() else None)==before, 'Qwen reader rewrote its input'
else:
    import aetherlab.__main__ as cli
    default='Derive the damped harmonic oscillator and visualize phase space.'
    prompt='Есеп: үдеу a = 3 м/с² — Қазақша'
    if case=='parse-no-smoke': assert cli.build_parser().parse_args([]).smoke is None
    elif case=='parse-default': assert cli.build_parser().parse_args(['--smoke']).smoke==default
    elif case=='parse-unicode': assert cli.build_parser().parse_args(['--smoke',prompt]).smoke==prompt
    elif case=='unknown-flag':
        cli.main(['--does-not-exist'])
        raise AssertionError('Unknown flag was not rejected')
    else:
        expected={'dispatch-default':default,'dispatch-unicode':prompt,'dispatch-empty':'','dispatch-whitespace':'  keep spaces  '}[case]
        received=[]
        class PipelineSpy:
            def __init__(self,settings): pass
            async def run(self,request):
                from aetherlab.core.models import ProblemRequest
                assert isinstance(request,ProblemRequest)
                received.append(request.prompt)
                return SimpleNamespace(cache_key='owned-cache',plan=SimpleNamespace(model_name='owned-plan',enabled=lambda:[]),
                    solver=SimpleNamespace(model_name='owned-solver',keywords=[]),rag=SimpleNamespace(hits=[]),
                    scene=SimpleNamespace(engine='owned-engine',status='compiled'),request=request)
        cli.AetherLabPipeline=PipelineSpy
        args=['--smoke'] if case=='dispatch-default' else ['--smoke',expected]
        assert cli.main(args)==0
        assert received==[expected], 'Actual smoke request did not preserve the CLI prompt'
secrets=('owned-qwen-key','owned-app-key','other-owned-key')
assert not any(secret in captured_logs.getvalue() for secret in secrets), 'Owned credentials reached diagnostic logging'
for log_path in base.rglob('*.log'):
    assert not any(secret in log_path.read_text(encoding='utf-8') for secret in secrets), 'Owned credentials reached a log file'
print(json.dumps({'case':case,'status':'PASS'}))
'''


def run_case(feature: str, case: str, base: Path) -> dict:
    assert case in CASE_REQUIREMENTS[feature]
    base.mkdir(parents=True)
    environment = {name:value for name,value in os.environ.items() if not name.startswith(
        ("AETHERLAB_","OPENAI_","QWEN_","DASHSCOPE_","MANIM_","GPT_","CHAT_","LLM_"))}
    environment.pop('OWNED_QWEN_KEY',None)
    environment.update({"AETHERLAB_DATA_DIR":str(base/'data'),"AETHERLAB_LIBRARY_DIR":str(base/'library'),
        "AETHERLAB_CHROMA_PATH":str(base/'chroma'),"AETHERLAB_CACHE_PATH":str(base/'cache.sqlite3'),
        "AETHERLAB_DISABLE_LEGACY_ENV":"1","AETHERLAB_QWEN_AUTOLOAD":"0",
        "QWEN_SETTINGS_PATH":str(base/'no-qwen.json'),"AETHERLAB_REFERENCE_SOURCES":str(base/'no-refs'),
        "AETHERLAB_WEB_REFS":"0"})
    completed = subprocess.run([sys.executable,"-c",CHILD,str(ROOT),str(base),case],cwd=base,env=environment,
        capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=45)
    if case=='unknown-flag':
        good=completed.returncode==2 and 'usage:' in completed.stderr and 'Traceback' not in completed.stderr
    elif case.endswith('qt-entrypoint'):
        good=(completed.returncode==2 and 'PyQt6' in completed.stderr and 'pip install' in completed.stderr
              and 'Traceback' not in completed.stderr)
        if case=='broken-qt-entrypoint': good=good and 'could not be loaded' in completed.stderr and 'is not installed' not in completed.stderr
    else:
        good=completed.returncode==0 and json.loads(completed.stdout.splitlines()[-1])['status']=='PASS'
    assert good, f"{feature}/{case}: child exit {completed.returncode}: {completed.stderr[-1600:]}"
    assert not any(key in completed.stdout+completed.stderr for key in ('owned-qwen-key','owned-app-key','other-owned-key'))
    return {"id":case,"status":"PASS","covers":sorted(CASE_REQUIREMENTS[feature][case]),
            "exit_code":completed.returncode,"stdout":completed.stdout,"stderr":completed.stderr}


def run_acceptance(output: Path, row: dict) -> dict:
    from tools.feature_acceptance import contract_hash

    feature=row['ID']
    before={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in FEATURE_SOURCES[feature]}
    with tempfile.TemporaryDirectory(prefix='startup-',dir=ROOT/'tmp') as folder:
        checks=[run_case(feature,case,Path(folder)/str(index)) for index,case in enumerate(CASE_REQUIREMENTS[feature])]
    after={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in FEATURE_SOURCES[feature]}
    assert before==after, 'Startup acceptance inputs changed during execution'
    evidence={'schema':'physlab.story_acceptance.v1','feature_id':feature,'status':'PASS','exit_code':0,
              'completed_at':datetime.now(UTC).isoformat(),'contract_sha256':contract_hash(row),
              'source_sha256':after,'checks':checks,'scope':DETAILS[feature]}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'path':output.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}
