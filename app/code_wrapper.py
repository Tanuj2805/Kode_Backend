"""
Code wrapper module to wrap user code with test cases for single-job execution.
Supports Python, JavaScript, Go, C++, Java, and C.
"""

import json
import re
from typing import List, Dict


def wrap_code_with_all_tests(user_code: str, test_cases: List[Dict], problem_slug: str, function_name: str, language: str) -> str:
    """
    Wrap user code with ALL test cases for single-job execution.
    
    Args:
        user_code: The user's solution code
        test_cases: List of test cases with 'input' and 'expected' fields
        problem_slug: Problem identifier (e.g., 'two_sum')
        function_name: Function name to call (e.g., 'twoSum')
        language: Programming language
    
    Returns:
        Wrapped code that executes all test cases and outputs JSON results
    """
    if language == "python":
        return wrap_python_with_all_tests(user_code, test_cases)
    elif language == "javascript":
        return wrap_javascript_with_all_tests(user_code, test_cases)
    elif language == "go":
        return wrap_go_with_all_tests(user_code, test_cases)
    elif language == "cpp":
        return wrap_cpp_with_all_tests(user_code, test_cases)
    elif language == "java":
        return wrap_java_with_all_tests(user_code, test_cases)
    elif language == "c":
        return wrap_c_with_all_tests(user_code, test_cases)
    else:
        # For unsupported languages, return original code
        return user_code


def wrap_python_with_all_tests(user_code: str, test_cases: List[Dict]) -> str:
    """
    Wrap Python code with test execution logic.
    Uses json.dumps for safe escaping of user code and test cases.
    """
    
    # Use json.dumps to safely embed test cases and user code as JSON strings
    test_cases_json = json.dumps(test_cases)
    user_code_json = json.dumps(user_code)
    
    wrapper = f'''import sys
import io
import json

# Test cases (parse JSON string to avoid true/false vs True/False issue)
test_cases = json.loads({test_cases_json!r})

# User code
user_code = {user_code_json}

results = []

for i, tc in enumerate(test_cases):
    try:
        # Redirect stdin to test input
        sys.stdin = io.StringIO(tc["input"])
        
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        
        # Execute user code in isolated namespace
        exec(user_code, {{}})
        
        # Get output
        actual_output = sys.stdout.getvalue().strip()
        sys.stdout = old_stdout
        
        # Compare output
        expected = tc.get("expected", tc.get("expected_output", "")).strip()
        passed = (actual_output == expected)
        
        results.append({{
            "test_case": i + 1,
            "passed": passed,
            "actual": actual_output,
            "expected": expected,
            "input": tc["input"]
        }})
        
        # Fail-fast: stop on first failure
        if not passed:
            break
            
    except Exception as e:
        sys.stdout = old_stdout
        results.append({{
            "test_case": i + 1,
            "passed": False,
            "error": str(e),
            "input": tc["input"]
        }})
        break

# Output results as JSON
print(json.dumps(results))
'''
    
    return wrapper


def wrap_javascript_with_all_tests(user_code: str, test_cases: List[Dict]) -> str:
    """
    Wrap JavaScript code with test execution logic.
    """
    
    test_cases_json = json.dumps(test_cases)
    user_code_json = json.dumps(user_code)
    
    wrapper = f'''const readline = require('readline');

// Test cases
const testCases = {test_cases_json};

// User code
const userCode = {user_code_json};

const results = [];

// Process each test case
for (let i = 0; i < testCases.length; i++) {{
    const tc = testCases[i];
    
    try {{
        // Mock stdin with test input
        const inputLines = tc.input.split('\\n');
        let lineIndex = 0;
        
        // Capture console.log output
        let output = '';
        const originalLog = console.log;
        console.log = (...args) => {{
            output += args.join(' ') + '\\n';
        }};
        
        // Execute user code
        eval(userCode);
        
        // Restore console.log
        console.log = originalLog;
        
        // Compare output
        const actualOutput = output.trim();
        const expected = (tc.expected || tc.expected_output || '').trim();
        const passed = (actualOutput === expected);
        
        results.push({{
            test_case: i + 1,
            passed: passed,
            actual: actualOutput,
            expected: expected,
            input: tc.input
        }});
        
        // Fail-fast
        if (!passed) break;
        
    }} catch (error) {{
        results.push({{
            test_case: i + 1,
            passed: false,
            error: error.toString(),
            input: tc.input
        }});
        break;
    }}
}}

// Output results as JSON
console.log(JSON.stringify(results));
'''
    
    return wrapper


def wrap_go_with_all_tests(user_code: str, test_cases: List[Dict]) -> str:
    """
    Wrap Go code with test execution logic.
    Simpler approach: Rename user's main to userMain and include all user code.
    """
    
    # Remove package main from user code (we'll add it)
    user_code_clean = re.sub(r'package\s+main\s*\n?', '', user_code, count=1)
    
    # Extract and remove import statements from user code
    import_pattern = r'import\s+(?:\([^)]*\)|"[^"]*")\s*\n?'
    user_imports = re.findall(import_pattern, user_code_clean, re.MULTILINE | re.DOTALL)
    user_code_no_imports = re.sub(import_pattern, '', user_code_clean, flags=re.MULTILINE | re.DOTALL)
    
    # Rename user's main function to userMain
    user_code_renamed = re.sub(r'\bfunc\s+main\s*\(', 'func userMain(', user_code_no_imports)
    
    # Build test cases data
    test_cases_go = "[]TestCase{\n"
    for tc in test_cases:
        input_escaped = tc.get("input", "").replace('"', '\\"').replace('\n', '\\n')
        expected_escaped = tc.get("expected", tc.get("expected_output", "")).replace('"', '\\"').replace('\n', '\\n')
        test_cases_go += f'\t\t{{Input: "{input_escaped}", Expected: "{expected_escaped}"}},\n'
    test_cases_go += "\t}"
    
    # Extract individual imports from user's import blocks
    user_import_list = []
    for imp in user_imports:
        # Handle both single import and multi-line import blocks
        if '(' in imp:
            # Multi-line import block: import ( ... )
            imports_content = re.search(r'\((.*?)\)', imp, re.DOTALL)
            if imports_content:
                for line in imports_content.group(1).split('\n'):
                    line = line.strip()
                    if line and line.startswith('"'):
                        user_import_list.append(line)
        else:
            # Single import: import "package"
            pkg = re.search(r'"[^"]+"', imp)
            if pkg:
                user_import_list.append(pkg.group(0))
    
    # Required wrapper imports
    wrapper_imports = {'"bytes"', '"encoding/json"', '"fmt"', '"os"', '"strings"'}
    
    # Combine user imports with wrapper imports (deduplicate)
    all_imports = wrapper_imports.union(set(user_import_list))
    imports_str = '\n\t'.join(sorted(all_imports))
    
    # Build wrapper
    wrapper = f'''package main

import (
\t{imports_str}
)

type TestCase struct {{
\tInput    string `json:"input"`
\tExpected string `json:"expected"`
}}

type Result struct {{
\tTestCase int    `json:"test_case"`
\tPassed   bool   `json:"passed"`
\tActual   string `json:"actual"`
\tExpected string `json:"expected"`
\tInput    string `json:"input"`
\tError    string `json:"error,omitempty"`
}}

// User's code (main renamed to userMain, all functions included)
{user_code_renamed}

func main() {{
\ttests := {test_cases_go}
\tresults := []Result{{}}
\t
\tfor i, test := range tests {{
\t\t// Redirect os.Stdin
\t\toldStdin := os.Stdin
\t\tr, w, _ := os.Pipe()
\t\tos.Stdin = r
\t\tw.Write([]byte(test.Input))
\t\tw.Close()
\t\t
\t\t// Capture os.Stdout
\t\toldStdout := os.Stdout
\t\tr2, w2, _ := os.Pipe()
\t\tos.Stdout = w2
\t\t
\t\t// Execute user's main
\t\tfunc() {{
\t\t\tdefer func() {{
\t\t\t\tif r := recover(); r != nil {{
\t\t\t\t\tos.Stdout = oldStdout
\t\t\t\t\tos.Stdin = oldStdin
\t\t\t\t\tresults = append(results, Result{{
\t\t\t\t\t\tTestCase: i + 1,
\t\t\t\t\t\tPassed:   false,
\t\t\t\t\t\tError:    fmt.Sprintf("%v", r),
\t\t\t\t\t\tInput:    test.Input,
\t\t\t\t\t}})
\t\t\t\t}}
\t\t\t}}()
\t\t\t
\t\t\tuserMain()
\t\t}}()
\t\t
\t\t// Restore and get output
\t\tw2.Close()
\t\tos.Stdout = oldStdout
\t\tos.Stdin = oldStdin
\t\t
\t\tvar buf bytes.Buffer
\t\t_, _ = buf.ReadFrom(r2)
\t\tactual := strings.TrimSpace(buf.String())
\t\texpected := strings.TrimSpace(test.Expected)
\t\t
\t\tpassed := (actual == expected)
\t\tresults = append(results, Result{{
\t\t\tTestCase: i + 1,
\t\t\tPassed:   passed,
\t\t\tActual:   actual,
\t\t\tExpected: expected,
\t\t\tInput:    test.Input,
\t\t}})
\t\t
\t\tif !passed {{
\t\t\tbreak
\t\t}}
\t}}
\t
\t// Output JSON
\tjsonData, _ := json.Marshal(results)
\tfmt.Println(string(jsonData))
}}
'''
    
    return wrapper


def wrap_cpp_with_all_tests(user_code: str, test_cases: List[Dict]) -> str:
    """
    Wrap C++ code with test execution logic.
    Embeds test cases and user code into a single file.
    """
    
    # Build test cases data
    test_cases_cpp = ""
    for tc in test_cases:
        input_escaped = tc.get("input", "").replace('"', '\\"').replace('\n', '\\n')
        expected_escaped = tc.get("expected", tc.get("expected_output", "")).replace('"', '\\"').replace('\n', '\\n')
        test_cases_cpp += f'\t\t{{"{input_escaped}", "{expected_escaped}"}},\n'
    
    # Extract user's main function and rename to userMain
    user_code_modified = user_code.replace("int main()", "int userMain()")
    
    wrapper = f'''#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <cstdio>
using namespace std;

struct TestCase {{
    string input;
    string expected;
}};

// User's code (main renamed to userMain)
{user_code_modified}

int main() {{
    vector<TestCase> tests = {{
{test_cases_cpp}
    }};
    
    cout << "[";
    for (size_t i = 0; i < tests.size(); i++) {{
        // Redirect cin
        istringstream input_stream(tests[i].input);
        streambuf* old_cin = cin.rdbuf(input_stream.rdbuf());
        
        // Redirect cout
        ostringstream output_stream;
        streambuf* old_cout = cout.rdbuf(output_stream.rdbuf());
        
        // Call user's main
        userMain();
        
        // Restore streams
        cin.rdbuf(old_cin);
        cout.rdbuf(old_cout);
        
        // Get output
        string actual = output_stream.str();
        if (!actual.empty() && actual.back() == '\\n') {{
            actual.pop_back();
        }}
        
        bool passed = (actual == tests[i].expected);
        
        // Output JSON
        if (i > 0) cout << ",";
        cout << "{{";
        cout << "\\"test_case\\":" << (i+1) << ",";
        cout << "\\"passed\\":" << (passed ? "true" : "false") << ",";
        cout << "\\"actual\\":\\"" << actual << "\\",";
        cout << "\\"expected\\":\\"" << tests[i].expected << "\\",";
        cout << "\\"input\\":\\"" << tests[i].input << "\\"";
        cout << "}}";
        
        if (!passed) break;
    }}
    cout << "]" << endl;
    
    return 0;
}}
'''
    
    return wrapper


def wrap_java_with_all_tests(user_code: str, test_cases: List[Dict]) -> str:
    """
    Wrap Java code with test execution logic.
    """
    
    # Build test cases data
    test_cases_java = ""
    for tc in test_cases:
        input_escaped = tc.get("input", "").replace('"', '\\"').replace('\n', '\\n')
        expected_escaped = tc.get("expected", tc.get("expected_output", "")).replace('"', '\\"').replace('\n', '\\n')
        test_cases_java += f'\t\tnew TestCase("{input_escaped}", "{expected_escaped}"),\n'
    
    # Extract user's main method and wrap in Solution class
    user_code_modified = user_code.replace("public static void main(String[] args)", "public static void userMain(String[] args)")
    
    wrapper = f'''import java.io.*;
import java.util.*;

class TestCase {{
    String input;
    String expected;
    TestCase(String input, String expected) {{
        this.input = input;
        this.expected = expected;
    }}
}}

class Solution {{
{indent_code(user_code_modified, 1)}
}}

public class Main {{
    public static void main(String[] args) throws Exception {{
        TestCase[] tests = {{
{test_cases_java}
        }};
        
        System.out.print("[");
        for (int i = 0; i < tests.length; i++) {{
            TestCase test = tests[i];
            
            // Redirect System.in
            ByteArrayInputStream inStream = new ByteArrayInputStream(test.input.getBytes());
            System.setIn(inStream);
            
            // Redirect System.out
            ByteArrayOutputStream outStream = new ByteArrayOutputStream();
            PrintStream ps = new PrintStream(outStream);
            System.setOut(ps);
            
            // Call user's main
            Solution.userMain(new String[0]);
            
            // Get output
            String actual = outStream.toString().trim();
            String expected = test.expected.trim();
            boolean passed = actual.equals(expected);
            
            // Output JSON
            if (i > 0) System.err.print(",");
            System.err.print("{{");
            System.err.print("\\"test_case\\":" + (i+1) + ",");
            System.err.print("\\"passed\\":" + passed + ",");
            System.err.print("\\"actual\\":\\"" + actual + "\\",");
            System.err.print("\\"expected\\":\\"" + expected + "\\",");
            System.err.print("\\"input\\":\\"" + test.input + "\\"");
            System.err.print("}}");
            
            if (!passed) break;
        }}
        System.err.println("]");
    }}
}}
'''
    
    return wrapper


def wrap_c_with_all_tests(user_code: str, test_cases: List[Dict]) -> str:
    """
    Wrap C code with test execution logic.
    """
    
    # Build test cases data
    test_cases_c = ""
    for tc in test_cases:
        input_escaped = tc.get("input", "").replace('"', '\\"').replace('\n', '\\n')
        expected_escaped = tc.get("expected", tc.get("expected_output", "")).replace('"', '\\"').replace('\n', '\\n')
        test_cases_c += f'\t\t{{"{input_escaped}", "{expected_escaped}"}},\n'
    
    # Extract user's main function and rename to userMain
    user_code_modified = user_code.replace("int main()", "int userMain()")
    
    wrapper = f'''#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {{
    char* input;
    char* expected;
}} TestCase;

// User's code (main renamed to userMain)
{user_code_modified}

int main() {{
    TestCase tests[] = {{
{test_cases_c}
    }};
    int num_tests = sizeof(tests) / sizeof(tests[0]);
    
    printf("[");
    for (int i = 0; i < num_tests; i++) {{
        // Create temp file for input
        FILE* input_file = tmpfile();
        fprintf(input_file, "%s", tests[i].input);
        rewind(input_file);
        
        // Redirect stdin
        FILE* old_stdin = stdin;
        stdin = input_file;
        
        // Create temp file for output
        FILE* output_file = tmpfile();
        FILE* old_stdout = stdout;
        stdout = output_file;
        
        // Call user's main
        userMain();
        
        // Restore stdout and get output
        stdout = old_stdout;
        rewind(output_file);
        char actual[1024] = {{}};
        if (fgets(actual, sizeof(actual), output_file)) {{
            // Remove trailing newline
            size_t len = strlen(actual);
            if (len > 0 && actual[len-1] == '\\n') actual[len-1] = '\\0';
        }}
        
        // Restore stdin
        stdin = old_stdin;
        fclose(input_file);
        fclose(output_file);
        
        // Compare
        int passed = (strcmp(actual, tests[i].expected) == 0);
        
        // Output JSON
        if (i > 0) printf(",");
        printf("{{");
        printf("\\"test_case\\":%d,", i+1);
        printf("\\"passed\\":%s,", passed ? "true" : "false");
        printf("\\"actual\\":\\"%s\\",", actual);
        printf("\\"expected\\":\\"%s\\",", tests[i].expected);
        printf("\\"input\\":\\"%s\\"", tests[i].input);
        printf("}}");
        
        if (!passed) break;
    }}
    printf("]\\n");
    
    return 0;
}}
'''
    
    return wrapper


def indent_code(code: str, levels: int) -> str:
    """Helper function to indent code by specified number of tab levels."""
    indent = "\t" * levels
    lines = code.split("\n")
    return "\n".join(indent + line if line.strip() else line for line in lines)
