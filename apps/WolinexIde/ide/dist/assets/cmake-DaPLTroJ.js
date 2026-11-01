import{o as e}from"./dist-DBErXIpE.js";import{c as t}from"./dist-DMmpOK1b.js";var n=new Set(`add_compile_definitions add_compile_options add_custom_command add_custom_target add_definitions
add_dependencies add_executable add_library add_link_options add_subdirectory add_test aux_source_directory
build_command build_name cmake_file_api cmake_host_system_information cmake_language cmake_minimum_required
cmake_parse_arguments cmake_path cmake_policy configure_file create_test_sourcelist
ctest_build ctest_configure ctest_coverage ctest_empty_binary_directory ctest_memcheck ctest_read_custom_files
ctest_run_script ctest_sleep ctest_start ctest_submit ctest_test ctest_update ctest_upload define_property
enable_language enable_testing exec_program execute_process export export_library_dependencies file
find_file find_library find_package find_path find_program fltk_wrap_ui get_cmake_property
get_directory_property get_filename_component get_property get_source_file_property get_target_property
get_test_property include include_directories include_external_msproject include_guard include_regular_expression
install install_files install_programs install_targets link_directories link_libraries list load_cache
load_command make_directory mark_as_advanced math message option output_required_files project qt_wrap_cpp
qt_wrap_ui remove remove_definitions separate_arguments set set_directory_properties set_property
set_source_files_properties set_target_properties set_tests_properties site_name source_group string
subdir_depends subdirs target_compile_definitions target_compile_features target_compile_options
 target_include_directories target_link_directories target_link_libraries target_link_options
 target_precompile_headers target_sources try_compile try_run unset use_mangled_mesa utility_source
variable_requires variable_watch write_file`.split(/\s+/)),r=new Set(`block break continue else elseif endblock endforeach endfunction endif endmacro endwhile
foreach function if macro return while`.split(/\s+/)),i=new Set(`VERSION LANGUAGES NAME COMMAND COMMANDS WORKING_DIRECTORY COMMENT DEPENDS OUTPUT OUTPUTS BYPRODUCTS
PRIVATE PUBLIC INTERFACE REQUIRED QUIET COMPONENTS OPTIONAL_COMPONENTS CONFIG MODULE EXACT GLOBAL
APPEND PROPERTY PROPERTIES CACHE INTERNAL FORCE PARENT_SCOPE PATH FILEPATH BOOL STRING
DIRECTORY DIRECTORIES FILE FILES TARGET TARGETS DESTINATION EXPORT NAMESPACE TYPE STATIC SHARED
MODULE OBJECT IMPORTED ALIAS EXCLUDE_FROM_ALL ALL BEFORE AFTER SYSTEM CONFIGURE_DEPENDS
AND OR NOT DEFINED EXISTS IS_DIRECTORY IS_SYMLINK IS_ABSOLUTE MATCHES LESS GREATER EQUAL
LESS_EQUAL GREATER_EQUAL STRLESS STRGREATER STREQUAL VERSION_LESS VERSION_GREATER VERSION_EQUAL
VERSION_LESS_EQUAL VERSION_GREATER_EQUAL IN_LIST COMMAND POLICY TARGET TEST`.split(/\s+/));function a(e,t){let{end:n,style:r}=t.bracket,i=e.string.indexOf(n,e.pos);return i<0?e.skipToEnd():(e.pos=i+n.length,t.bracket=null),r}function o(e){let t=e.match(/^\$(?:ENV|CACHE)?\{/),n=!t&&e.match(/^\$</);if(!t&&!n)return!1;let r=1;for(;!e.eol()&&r;)if(n&&e.match(`$<`))r++;else{let n=e.next();t&&n===`{`&&r++,n===(t?`}`:`>`)&&r--}return!0}var s={name:`cmake`,startState:()=>({quoted:!1,bracket:null,depth:0,definition:!1}),copyState:e=>({...e,bracket:e.bracket&&{...e.bracket}}),languageData:{commentTokens:{line:`#`,block:{open:`#[[`,close:`]]`}}},tokenTable:{command:e.standard(e.function(e.variableName)),cmakeVariable:e.standard(e.variableName),expansion:e.special(e.variableName),functionDefinition:e.function(e.definition(e.variableName))},token(e,t){if(t.bracket)return a(e,t);if(o(e))return`expansion`;if(e.eat(`\\`))return e.next(),`escape`;if(e.eat(`"`))return t.quoted=!t.quoted,`string`;if(t.quoted){for(;!e.eol()&&!/["\\]/.test(e.peek())&&!e.match(/^\$(?:(?:ENV|CACHE)?\{|<)/,!1);)e.next();return`string`}if(e.eatSpace())return null;let s=e.match(/^(#?)\[(=*)\[/);if(s){let[,n,r]=s;return t.bracket={end:`]${r}]`,style:n?`comment`:`string`},a(e,t)}if(e.eat(`#`))return e.skipToEnd(),`comment`;if(e.eat(`(`))return t.depth++,`paren`;if(e.eat(`)`))return t.depth=Math.max(0,t.depth-1),t.definition=!1,`paren`;let c=e.match(/^[^\s()#"\\$]+/);if(c){let a=c[0];if(t.depth===0&&/^[A-Za-z_]\w*$/.test(a)&&e.match(/^\s*\(/,!1)){let e=a.toLowerCase();return t.definition=e===`function`||e===`macro`,r.has(e)?`keyword`:n.has(e)?`command`:`variableName.function`}return t.definition?(t.definition=!1,`functionDefinition`):/^[+-]?\d+(?:\.\d+)*(?:\.\.\.<?\d+(?:\.\d+)*)?$/.test(a)?`number`:/^(?:ON|OFF|TRUE|FALSE|YES|NO|Y|N|IGNORE|NOTFOUND)$/i.test(a)?`bool`:/^(?:CMAKE|PROJECT|CTEST|CPACK)_\w+$/.test(a)?`cmakeVariable`:i.has(a)?`keyword`:null}return e.next(),null}},c=t.define(s);export{c as cmakeLanguage};
//# sourceMappingURL=cmake-DaPLTroJ.js.map