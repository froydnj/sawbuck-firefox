# Copyright 2009 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

{
  'targets': [
    {
      'target_name': 'benchmark',
      'type': 'none',
      'variables': {
        'benchmark_sources': [
          'benchmark.py',
          'chrome_control.py',
          'chrome_control_test.py',
          'firefox_control.py',
          'event_counter.py',
          'optimize.py',
          'runner.py',
          'setup.py',
          'zip_benchmark.py',
        ],
        'setup_file': [
          'setup.py',
        ],
        'success_file': [
          '<(PRODUCT_DIR)/Benchmark-egg-success.txt',
        ],
        'script_file': [
          '<(DEPTH)/syzygy/build/build_egg.py',
        ],
      },
      'sources': [
        '<@(benchmark_sources)',
      ],
      'dependencies': [
        '<(DEPTH)/syzygy/snapshot/snapshot.gyp:run_in_snapshot',
        '<(DEPTH)/syzygy/snapshot/snapshot.gyp:run_in_snapshot_xp',
        '<(DEPTH)/syzygy/snapshot/snapshot.gyp:run_in_snapshot_x64',
        '<(DEPTH)/syzygy/call_trace/call_trace.gyp:call_trace',
        '<(DEPTH)/syzygy/call_trace/call_trace.gyp:call_trace_control',
        '<(DEPTH)/syzygy/instrument/instrument.gyp:instrument',
        '<(DEPTH)/syzygy/relink/relink.gyp:relink',
        '<(DEPTH)/syzygy/reorder/reorder.gyp:reorder',
        '<(DEPTH)/syzygy/py/py.gyp:virtualenv',
        '<(DEPTH)/syzygy/py/etw_db/etw_db.gyp:etw',
        '<(DEPTH)/syzygy/py/etw_db/etw_db.gyp:etw_db',
      ],
      'actions': [
        {
          'action_name': 'build_benchmark',
          'msvs_cygwin_shell': 0,
          'inputs': [
            '<(script_file)',
            '<(setup_file)',
            '<@(benchmark_sources)',
          ],
          'outputs': [
            '<(success_file)',
          ],
          'action': [
            '<(PRODUCT_DIR)/py/scripts/python',
            '<(script_file)',
            '--setup-file', '<(setup_file)',
            '--build-dir', '<(PRODUCT_DIR)/temp/benchmark',
            '--success-file', '<(success_file)',
            '--',
            'install_data',
                '--exe-dir', '<(PRODUCT_DIR)',
          ],
        },
      ],
    },
    {
      'target_name': 'benchmark_zip',
      'type': 'none',
      'dependencies': [
        'benchmark',
        '<(DEPTH)/sawbuck/py/etw/etw.gyp:etw',
        '<(DEPTH)/syzygy/py/etw_db/etw_db.gyp:etw_db',
        '<(DEPTH)/syzygy/scripts/scripts.gyp:setuptools',
      ],
      'actions': [
        {
          'action_name': 'create_benchmark_zip',
          'msvs_cygwin_shell': 0,
          'inputs': [
            'zip_benchmark.py',
            # The -success files are modified on successful egging,
            # and have a fixed name. We use them to trigger re-zipping
            # rather than the eggs, which have variable file names.
            '<(PRODUCT_DIR)/Benchmark-egg-success.txt',
            '<(PRODUCT_DIR)/ETW-egg-success.txt',
            '<(PRODUCT_DIR)/ETW-Db-egg-success.txt',
            '<(PRODUCT_DIR)/setuptools-0.6c11-py2.6.egg',
          ],
          'outputs': [
            '<(PRODUCT_DIR)/benchmark.bat',
            '<(PRODUCT_DIR)/benchmark.zip',
            '<(PRODUCT_DIR)/optimize.bat',
          ],
          'action': [
            '<(PRODUCT_DIR)/py/scripts/python',
            'zip_benchmark.py',
            '--root-dir',
            '<(PRODUCT_DIR)',
          ],
        },
      ],
    },
  ]
}
