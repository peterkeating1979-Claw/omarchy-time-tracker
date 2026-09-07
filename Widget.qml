import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: root
    property var bar
    property string moduleName
    property var settings
    property var trackerState: ({running: null, selected_company: null, selected_project: null})
    property var companies: []
    property var projects: []
    onCompaniesChanged: {
        if (popup.open && popup.companyName === "" && companies.length > 0)
            popup.companyName = trackerState.selected_company || companies[0].name
    }
    property string errorText: ""
    property var reportData: null
    property string pdfPath: ""
    property string obsidianPath: ""
    property string obsidianUri: ""
    property real now: Date.now()
    readonly property bool vertical: bar ? bar.vertical : false
    readonly property real elapsed: trackerState.running ? Math.max(0, (now - Date.parse(trackerState.running.start)) / 1000) : 0
    readonly property string bridge: decodeURIComponent(Qt.resolvedUrl("bridge.py").toString().replace(/^file:\/\//, ""))
    implicitWidth: vertical ? (bar ? bar.barSize : 26) : Math.min(260, label.implicitWidth + 16)
    implicitHeight: bar ? bar.barSize : 26

    function duration(seconds) {
        var s = Math.floor(seconds || 0)
        return Math.floor(s / 3600) + ":" + String(Math.floor(s / 60) % 60).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0")
    }
    function close() { popup.open = false }
    function toggle() { popup.open = !popup.open; refresh() }
    function triggerPress(button) { toggle() }
    function refresh() { if (!worker.running) request([]) }
    function request(args) {
        if (worker.running) return
        worker.isAction = args.length > 0
        worker.received = false
        worker.command = ["/usr/bin/python3", "-E", "-s", "-B", root.bridge, JSON.stringify({args: args})]
        worker.running = true
    }

    IpcHandler {
        target: "peter.time-tracker"
        function toggle(): void { root.toggle() }
        function open(): void { popup.open = true; root.refresh() }
        function close(): void { root.close() }
        function status(): string { return JSON.stringify({state: root.trackerState, error: root.errorText, open: popup.open}) }
    }

    Process {
        id: worker
        property bool isAction: false
        property bool received: false
        onRunningChanged: {
            if (running) watchdog.restart()
            else watchdog.stop()
        }
        stdout: StdioCollector {
            waitForEnd: true
            onStreamFinished: {
                try {
                    var data = JSON.parse(text)
                    worker.received = true
                    if (!data.ok) { root.errorText = data.error; return }
                    if (worker.isAction) root.errorText = ""
                    if (data.result && data.result.warning) root.errorText = data.result.warning
                    root.trackerState = data.status
                    root.companies = data.companies
                    root.projects = data.projects
                    root.now = Date.now()
                    if (data.result && data.result.period) root.reportData = data.result
                    if (data.result && data.result.pdf_path) root.pdfPath = data.result.pdf_path
                    if (data.result && data.result.obsidian_vault !== undefined) popup.setVault(data.result.obsidian_vault)
                    if (data.result && data.result.obsidian_path) {
                        root.obsidianPath = data.result.obsidian_path
                        root.obsidianUri = data.result.obsidian_uri
                    }
                } catch (e) { root.errorText = "Unable to read timer data: " + e }
            }
        }
        onExited: function(exitCode) {
            if (exitCode !== 0 && !received) root.errorText = "Time Tracker could not load its data (exit " + exitCode + ")."
        }
    }
    Timer {
        id: watchdog
        interval: 60000
        onTriggered: {
            worker.running = false
            root.errorText = "Time Tracker timed out. Check status before retrying an action."
        }
    }
    Timer { interval: 5000; running: true; repeat: true; triggeredOnStart: true; onTriggered: root.refresh() }
    Timer { interval: 1000; running: root.trackerState.running !== null; repeat: true; onTriggered: root.now = Date.now() }

    Text {
        id: label
        anchors.centerIn: parent
        width: Math.min(244, implicitWidth)
        text: root.vertical ? "󱎫" : (root.errorText ? "󱎫 Tracker !" : root.trackerState.running ? "󱎫 " + root.duration(root.elapsed) + " · " + root.trackerState.running.company : "󱎫 Time Tracker")
        textFormat: Text.PlainText
        elide: Text.ElideRight
        color: bar ? bar.foreground : "white"
        font.family: bar ? bar.fontFamily : "monospace"
        font.pixelSize: 12
        font.bold: root.trackerState.running !== null
    }

    TrackerPopup {
        id: popup
        anchorItem: root
        bar: root.bar
        owner: root
        busy: worker.running
    }
}
