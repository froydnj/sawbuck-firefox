// Copyright 2009 Google Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
// Log viewer window declaration.
#ifndef SAWBUCK_VIEWER_VIEWER_WINDOW_H_
#define SAWBUCK_VIEWER_VIEWER_WINDOW_H_

#include <atlbase.h>
#include <atlcrack.h>
#include <atlapp.h>
#include <atlctrls.h>
#include <atlframe.h>
#include <atlmisc.h>
#include <atlres.h>
#include <atlstr.h>
#include <string>
#include <vector>
#include "base/event_trace_controller_win.h"
#include "base/scoped_ptr.h"
#include "base/lock.h"
#include "base/thread.h"
#include "sawbuck/sym_util/module_cache.h"
#include "sawbuck/sym_util/symbol_cache.h"
#include "sawbuck/viewer/log_viewer.h"
#include "sawbuck/viewer/resource.h"
#include "sawbuck/viewer/kernel_log_consumer.h"
#include "sawbuck/viewer/log_consumer.h"


// Log level settings for a provider.
struct ProviderSettings {
  GUID provider_guid;
  std::wstring provider_name;
  UCHAR log_level;
};

class ViewerWindow
    : public CFrameWindowImpl<ViewerWindow>,
      public KernelModuleEvents,
      public LogEvents,
      public ILogView,
      public ISymbolLookupService,
      public CIdleHandler,
      public CMessageFilter,
      public CUpdateUI<ViewerWindow> {
 public:
  typedef CFrameWindowImpl<ViewerWindow> SuperFrame;

  DECLARE_FRAME_WND_CLASS(NULL, IDR_MAIN_FRAME);
  BEGIN_MSG_MAP_EX(ViewerWindow)
    MSG_WM_CREATE(OnCreate)
    MSG_WM_DESTROY(OnDestroy)
    COMMAND_ID_HANDLER(ID_FILE_EXIT, OnExit)
    COMMAND_ID_HANDLER(ID_APP_ABOUT, OnAbout)
    COMMAND_ID_HANDLER(ID_LOG_CONFIGUREPROVIDERS, OnConfigureProviders)
    COMMAND_ID_HANDLER(ID_LOG_CAPTURE, OnToggleCapture)
    CHAIN_MSG_MAP(CUpdateUI<ViewerWindow>);
    CHAIN_MSG_MAP(SuperFrame);
  END_MSG_MAP()

  BEGIN_UPDATE_UI_MAP(ViewerWindow)
    UPDATE_ELEMENT(ID_LOG_CAPTURE, UPDUI_MENUBAR)
  END_UPDATE_UI_MAP()

  ViewerWindow();
  ~ViewerWindow();

  // ILogView implementation
  virtual int GetNumRows();
  virtual int GetSeverity(int row);
  virtual DWORD GetProcessId(int row);
  virtual DWORD GetThreadId(int row);
  virtual base::Time GetTime(int row);
  virtual std::string GetFileName(int row);
  virtual int GetLine(int row);
  virtual std::string GetMessage(int row);
  virtual void GetStackTrace(int row, std::vector<void*>* stack_trace);

  virtual void Register(ILogViewEvents* event_sink,
                        int* registration_cookie);
  virtual void Unregister(int registration_cookie);

  // ISymbolLookupService implementation
  virtual bool ResolveAddress(sym_util::ProcessId process_id,
                              const base::Time& time,
                              sym_util::Address address,
                              sym_util::Symbol* symbol);

 private:
  LRESULT OnExit(WORD code, LPARAM lparam, HWND wnd, BOOL& handled);
  LRESULT OnAbout(WORD code, LPARAM lparam, HWND wnd, BOOL& handled);
  LRESULT OnConfigureProviders(WORD code, LPARAM lparam, HWND wnd,
      BOOL& handled);
  LRESULT OnToggleCapture(WORD code, LPARAM lparam, HWND wnd, BOOL& handled);

  virtual BOOL OnIdle();
  virtual BOOL PreTranslateMessage(MSG* pMsg);
  int OnCreate(LPCREATESTRUCT lpCreateStruct);
  void OnDestroy();

  // Host for compile-time asserts on privates.
  static void CompileAsserts();

  void StopCapturing();
  bool StartCapturing();

 private:
  // Fwd.
  void OnLogMessage(UCHAR level,
                    DWORD process_id,
                    DWORD thread_id,
                    LARGE_INTEGER time_stamp,
                    size_t num_traces,
                    void** trace,
                    size_t length,
                    const char* message);
  virtual void OnModuleIsLoaded(DWORD process_id,
                                const base::Time& time,
                                const ModuleInformation& module_info);
  virtual void OnModuleUnload(DWORD process_id,
                              const base::Time& time,
                              const ModuleInformation& module_info);
  virtual void OnModuleLoad(DWORD process_id,
                            const base::Time& time,
                            const ModuleInformation& module_info);

  void EnableProviders(const std::vector<ProviderSettings>& settings);
  void ReadProviderSettings(std::vector<ProviderSettings>* settings);
  void WriteProviderSettings(const std::vector<ProviderSettings>& settings);

  struct LogMessage {
    UCHAR level;
    DWORD process_id;
    DWORD thread_id;
    base::Time time_stamp;
    std::string file;
    int line;
    std::string message;
    std::vector<void*> trace;
  };

  // We dedicate a thread to the symbol lookup work.
  base::Thread symbol_lookup_worker_;

  Lock list_lock_;
  typedef std::vector<LogMessage> LogMessageList;
  LogMessageList log_messages_;  // Under list_lock_.
  bool log_message_size_dirty_;  // Under list_lock_.

  typedef std::map<int, ILogViewEvents*> EventSinkMap;
  EventSinkMap event_sinks_;  // Under list_lock_.
  int next_sink_cookie_;  // Under list_lock_.

  Lock symbol_lock_;
  sym_util::ModuleCache module_cache_;  // Under symbol_lock_.
  typedef std::map<sym_util::ModuleCache::ModuleLoadStateId,
      sym_util::SymbolCache> SymbolCacheMap;

  // We keep a cache of symbol cache instances keyed on module
  // load state id with an lru replacement policy.
  static const size_t kMaxCacheSize = 10;
  typedef std::vector<sym_util::ModuleCache::ModuleLoadStateId> LoadStateVector;
  LoadStateVector lru_module_id_;
  SymbolCacheMap symbol_caches_;


  // The list view control that displays log_messages_.
  LogViewer log_viewer_;

  // Controller for the logging session.
  EtwTraceController log_controller_;

  // Log level settings for the providers we know of.
  std::vector<ProviderSettings> settings_;

  // Controller for the kernel logging session.
  EtwTraceController kernel_controller_;

  // NULL until StartConsuming. Valid until StopConsuming.
  scoped_ptr<LogConsumer> log_consumer_;
  scoped_ptr<KernelLogConsumer> kernel_consumer_;
  CHandle log_consumer_thread_;
  CHandle kernel_consumer_thread_;
};

#endif  // SAWBUCK_VIEWER_VIEWER_WINDOW_H_