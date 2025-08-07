import React, { useState, useRef, useEffect } from "react";

const ChatWidget = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const messagesEndRef = useRef(null);

  const appendMessage = (text, isUser = true) => {
    setMessages((prev) => [...prev, { text, isUser }]);
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text) return;

    appendMessage(text, true);
    setInput("");

    try {
      const res = await fetch("http://3.71.28.18:5000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text }),
      });
      const data = await res.json();
      appendMessage(data.answer || "🤖 暂时无法回答", false);
    } catch (err) {
      appendMessage("⚠️ 网络异常，请稍后再试", false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") sendMessage();
  };

  return (
    <div className="fixed bottom-4 right-4 z-50">
      {isOpen ? (
        <div className="w-80 h-96 bg-white rounded-2xl shadow-lg flex flex-col overflow-hidden">
          <div className="bg-blue-600 text-white p-3 flex justify-between items-center">
            <span className="font-semibold">🤖 智能客服</span>
            <button onClick={() => setIsOpen(false)}>✖</button>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-gray-50">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`p-2 rounded-xl max-w-[75%] ${
                  msg.isUser
                    ? "bg-blue-500 text-white self-end ml-auto"
                    : "bg-gray-200 text-black self-start"
                }`}
              >
                {msg.text}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
          <div className="p-2 border-t flex">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              className="flex-1 px-3 py-2 rounded-l-lg border border-gray-300 focus:outline-none"
              placeholder="请输入..."
            />
            <button
              onClick={sendMessage}
              className="bg-blue-500 text-white px-4 rounded-r-lg hover:bg-blue-600"
            >
              发送
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setIsOpen(true)}
          className="bg-blue-600 text-white px-4 py-2 rounded-full shadow-lg hover:bg-blue-700"
        >
          💬 聊天
        </button>
      )}
    </div>
  );
};

export default ChatWidget;