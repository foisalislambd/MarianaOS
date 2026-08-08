"""Quick logic checks for provider message conversion."""

from __future__ import annotations

from core.llm_types import openai_tools_to_declarations
from core.providers.anthropic_provider import AnthropicProvider
from core.providers.gemini import GeminiProvider, _parse_data_url, _to_plain_dict
from core.providers.openai_compat import _strip_private


def main() -> None:
    assert _to_plain_dict({"a": 1, "b": [2]}) == {"a": 1, "b": [2]}
    assert _to_plain_dict(None) == {}
    assert _parse_data_url("data:image/jpg;base64,QQ==")[0] == "image/jpeg"

    m = {
        "role": "assistant",
        "content": "hi",
        "_native": "X",
        "_tool_names": {"a": "b"},
        "tool_calls": [],
    }
    cleaned = _strip_private(m)
    assert "_native" not in cleaned and cleaned["content"] == "hi"

    gp = object.__new__(GeminiProvider)
    system, contents = GeminiProvider._messages_to_contents(
        gp,
        [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hello"},
            {
                "role": "assistant",
                "content": None,
                "_native": "NATIVE_OBJ",
                "tool_calls": [
                    {
                        "id": "1",
                        "type": "function",
                        "function": {"name": "take_screenshot", "arguments": "{}"},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "1",
                "name": "take_screenshot",
                "content": '{"success": true}',
            },
        ],
    )
    assert system == "sys"
    assert contents[0].role == "user"
    assert contents[1] == "NATIVE_OBJ"
    assert contents[2].role == "user"
    assert contents[2].parts[0].function_response.name == "take_screenshot"
    print("gemini history conversion: ok")

    ap = object.__new__(AnthropicProvider)
    sys, msgs = AnthropicProvider._split_system(
        ap,
        [
            {"role": "system", "content": "S"},
            {"role": "user", "content": "U"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "t1",
                        "type": "function",
                        "function": {"name": "x", "arguments": '{"a": 1}'},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "t1",
                "name": "x",
                "content": '{"ok": true}',
            },
        ],
    )
    assert sys == "S"
    assert msgs[1]["content"][0]["type"] == "tool_use"
    assert msgs[2]["content"][0]["type"] == "tool_result"
    print("anthropic history conversion: ok")

    decls = openai_tools_to_declarations(
        [
            {
                "type": "function",
                "function": {
                    "name": "n",
                    "description": "d",
                    "parameters": {"type": "object"},
                },
            }
        ]
    )
    assert decls[0]["name"] == "n"
    print("all checks passed")


if __name__ == "__main__":
    main()
