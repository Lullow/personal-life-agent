"""LongMemEval's grading templates, for the two question types measured.

ADR 0008 copies them verbatim, so that grading differs from LongMemEval's own
only where the record says it does: a system prompt asking for JSON, and a
verdict read from that JSON rather than a search for the word "yes".

Source: github.com/xiaowu0162/LongMemEval, ``src/evaluation/evaluate_qa.py``,
``get_anscheck_prompt``, at commit d0c699faf593726d96a6c75768e0fd2016d1feb8.
The strings below are that function's templates for ``single-session-user``
and ``knowledge-update``, unchanged. Its licence follows, as it requires.
"""

# MIT License
#
# Copyright (c) 2024 Di Wu
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

TEMPLATES = {
    "single-session-user": 'I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response is equivalent to the correct answer or contains all the intermediate steps to get the correct answer, you should also answer yes. If the response only contains a subset of the information required by the answer, answer no. \n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only.',
    "knowledge-update": 'I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response contains some previous information along with an updated answer, the response should be considered as correct as long as the updated answer is the required answer.\n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only.',
}


def grading_prompt(question_type: str, question: str, answer: str, response: str) -> str:
    """Fill the template exactly as ``get_anscheck_prompt`` does."""
    return TEMPLATES[question_type].format(question, answer, response)
