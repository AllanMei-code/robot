function appendMessage(text, isUser = true) {
    const messageDiv = document.createElement("div");
    messageDiv.className = isUser ? "user-message" : "bot-message";
    messageDiv.innerText = text;
    document.getElementById("chat-messages").appendChild(messageDiv);
}

async function sendMessage() {
    const input = document.getElementById("chat-input");
    const text = input.value.trim();
    if (!text) return;
    appendMessage(text, true);
    input.value = "";

    try {
        const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question: text }),
        });
        const data = await res.json();
        appendMessage(data.answer || "🤖 暂时无法回答", false);
    } catch (err) {
        appendMessage("⚠️ 网络异常，请稍后再试", false);
    }
}
