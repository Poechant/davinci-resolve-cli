# vhs script — render demo.gif from a fresh terminal.
#
# Prerequisites:
#   brew install vhs           # or see https://github.com/charmbracelet/vhs
#   pipx install davinci-resolve-cli   # or have `dvr` on PATH
#   Launch DaVinci Resolve Studio with at least one project open.
#
# Generate:
#   vhs docs/demo.tape         # writes docs/demo.gif
#
# Re-record any time the UX changes — keep the gif < 2 MB so README loads fast.

Output docs/demo.gif

Set FontSize 14
Set Width 960
Set Height 540
Set Theme "Catppuccin Mocha"
Set Padding 16

Type "dvr doctor --format json | jq '{version, edition, bridgeStatus}'"
Sleep 500ms
Enter
Sleep 2s

Type "dvr project current --format json"
Sleep 500ms
Enter
Sleep 2s

Type "dvr render presets --format json | head -3"
Sleep 500ms
Enter
Sleep 2s

Type "dvr timeline marker add --at 00:00:01:00 --note 'review' --color Green --format json"
Sleep 500ms
Enter
Sleep 2s

Type "dvr mcp # then Ctrl-D from your MCP client"
Sleep 1s
