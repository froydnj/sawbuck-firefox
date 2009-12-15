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
// Declares the types and structures we use in symbol utils.
#ifndef SAWBUCK_SYM_UTIL_TYPES_H_
#define SAWBUCK_SYM_UTIL_TYPES_H_

#include <windows.h>
#include <string>

namespace sym_util {

// We use 64 bit addreses throughout.
typedef ULONGLONG Address;
typedef ULONGLONG ModuleBase;

typedef DWORD ModuleSize;
typedef DWORD ModuleTimeDateStamp;
typedef DWORD ModuleChecksum;

typedef DWORD ProcessId;

// This is the information we pass around for a module.
struct ModuleInformation {
  ModuleBase base_address;
  ModuleSize module_size;
  ModuleChecksum image_checksum;
  ModuleTimeDateStamp time_date_stamp;
  std::wstring image_file_name;

  bool operator < (const ModuleInformation& o) const;
};

// A resolved symbol.
struct Symbol {
  Symbol() : offset(0), line(0) {
  }

  std::wstring module;
  std::wstring name;
  size_t offset;
  std::wstring file;
  size_t line;
};

}  // namespace types

#endif  // SAWBUCK_SYM_UTIL_TYPES_H_