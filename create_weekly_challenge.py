"""
Script to create a new weekly challenge
Usage: python create_weekly_challenge.py
"""

import asyncio
from datetime import datetime, timedelta
from app.database import get_database

async def create_challenge():
    db = get_database()
    
    # Example: Create a new weekly challenge
    challenge = {
        "week_number": 45,  # Change this
        "year": 2025,  # Change this
        "title": "Week 45 Challenge - Algorithms",  # Change this
        "description": "Practice essential algorithms this week",  # Change this
        "status": "upcoming",  # upcoming, active, or completed
        "start_date": datetime(2025, 11, 10, 0, 0, 0),  # Change this
        "end_date": datetime(2025, 11, 16, 23, 59, 59),  # Change this
        "created_at": datetime.utcnow(),
        "total_participants": 0,
        "questions": [
            {
                "question_number": 1,
                "title": "Binary Search",
                "difficulty": "Easy",
                "description": "Implement binary search algorithm to find an element in a sorted array.",
                "examples": [
                    {
                        "input": "Array: [1, 3, 5, 7, 9, 11, 13, 15, 17, 19]\nTarget: 7",
                        "output": "3",
                        "explanation": "The target 7 is at index 3"
                    }
                ],
                "input_format": "Line 1: Space-separated sorted integers\nLine 2: Target integer",
                "output_format": "Index of target (or -1 if not found)",
                "constraints": "1 ≤ array length ≤ 10^5\n-10^9 ≤ elements ≤ 10^9",
                "hints": [
                    "Start with the middle element",
                    "Compare target with middle element",
                    "Eliminate half of the array in each step"
                ],
                "test_cases": [
                    {
                        "input": "1 3 5 7 9 11 13 15 17 19\n7",
                        "expected": "3",
                        "hidden": False
                    },
                    {
                        "input": "1 3 5 7 9 11 13 15 17 19\n15",
                        "expected": "7",
                        "hidden": False
                    },
                    {
                        "input": "1 3 5 7 9\n2",
                        "expected": "-1",
                        "hidden": True
                    },
                    {
                        "input": "2 4 6 8 10 12 14\n12",
                        "expected": "5",
                        "hidden": True
                    },
                    {
                        "input": "5\n5",
                        "expected": "0",
                        "hidden": True
                    }
                ],
                "starter_code": {
                    "python": "import sys\n\n# Read input\narr = list(map(int, sys.stdin.readline().strip().split()))\ntarget = int(sys.stdin.readline().strip())\n\n# Binary search implementation\ndef binary_search(arr, target):\n    # Write your code here\n    pass\n\nresult = binary_search(arr, target)\nprint(result)",
                    "javascript": "const readline = require('readline');\nconst rl = readline.createInterface({input: process.stdin});\n\nlet lines = [];\nrl.on('line', (line) => {\n    lines.push(line);\n});\n\nrl.on('close', () => {\n    const arr = lines[0].split(' ').map(Number);\n    const target = parseInt(lines[1]);\n    \n    function binarySearch(arr, target) {\n        // Write your code here\n    }\n    \n    console.log(binarySearch(arr, target));\n});",
                    "java": "import java.util.*;\n\npublic class Solution {\n    public static int binarySearch(int[] arr, int target) {\n        // Write your code here\n        return -1;\n    }\n    \n    public static void main(String[] args) {\n        Scanner sc = new Scanner(System.in);\n        String[] input = sc.nextLine().split(\" \");\n        int[] arr = new int[input.length];\n        for (int i = 0; i < input.length; i++) {\n            arr[i] = Integer.parseInt(input[i]);\n        }\n        int target = sc.nextInt();\n        System.out.println(binarySearch(arr, target));\n    }\n}",
                    "cpp": "#include <iostream>\n#include <vector>\n#include <sstream>\nusing namespace std;\n\nint binarySearch(vector<int>& arr, int target) {\n    // Write your code here\n    return -1;\n}\n\nint main() {\n    string line;\n    getline(cin, line);\n    istringstream iss(line);\n    vector<int> arr;\n    int num;\n    while (iss >> num) arr.push_back(num);\n    \n    int target;\n    cin >> target;\n    \n    cout << binarySearch(arr, target) << endl;\n    return 0;\n}",
                    "c": "#include <stdio.h>\n\nint binarySearch(int arr[], int n, int target) {\n    // Write your code here\n    return -1;\n}\n\nint main() {\n    int arr[100], n = 0, num;\n    while (scanf(\"%d\", &num) == 1) {\n        arr[n++] = num;\n        if (getchar() == '\\n') break;\n    }\n    int target;\n    scanf(\"%d\", &target);\n    printf(\"%d\\n\", binarySearch(arr, n, target));\n    return 0;\n}"
                },
                "points": 15,
                "time_limit": 2000,
                "memory_limit": 128000
            },
            # Add more questions here...
        ]
    }
    
    try:
        result = await db.weekly_challenges.insert_one(challenge)
        print(f"✅ Challenge created successfully!")
        print(f"Challenge ID: {result.inserted_id}")
        print(f"Week: {challenge['week_number']}, Year: {challenge['year']}")
        print(f"Title: {challenge['title']}")
        print(f"Status: {challenge['status']}")
        print(f"Questions: {len(challenge['questions'])}")
    except Exception as e:
        print(f"❌ Error creating challenge: {e}")

if __name__ == "__main__":
    asyncio.run(create_challenge())











