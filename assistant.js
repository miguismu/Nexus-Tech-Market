"use strict";

const chatPanel = document.querySelector("#chat-panel");
const chatLauncher = document.querySelector("#chat-launcher");
const chatMessages = document.querySelector("#chat-messages");
const chatInput = document.querySelector("#chat-input");
const voiceInputButton = document.querySelector("#chat-voice-input");
const voiceToggleButton = document.querySelector("#chat-voice-toggle");
const voiceStatus = document.querySelector("#chat-voice-status");
const orbStage = document.querySelector("#chat-orb-stage");
const orbCaption = document.querySelector("#orb-caption");
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let voiceOutputEnabled = false;
let recognition = null;
let microphoneEnabled = false;
let recognitionRunning = false;
let responsePending = false;
let recognitionSubmitted = false;
let activeUtterance = null;

function setOrbState(state) {
  orbStage.classList.remove("is-speaking", "is-listening", "is-thinking");
  if (state) orbStage.classList.add(state);
  if (state === "is-listening") orbCaption.textContent = "Te escucho…";
  else if (state === "is-thinking") orbCaption.textContent = "Procesando…";
  else if (state === "is-speaking") orbCaption.textContent = "Hablando";
  else orbCaption.textContent = "En línea · Escríbeme o háblame";
}

function setVoiceStatus(message) {
  voiceStatus.textContent = message;
}

function setVoiceOutput(enabled, announce = false) {
  voiceOutputEnabled = enabled;
  localStorage.setItem("nexus-voice-output-v2", String(enabled));
  voiceToggleButton.setAttribute("aria-pressed", String(enabled));
  voiceToggleButton.setAttribute("aria-label", enabled ? "Desactivar micrófono y respuestas por voz" : "Activar micrófono y respuestas por voz");
  voiceToggleButton.title = enabled ? "Desactivar micrófono · Español Colombia" : "Activar micrófono y respuestas por voz · Español Colombia";
  if (!enabled && "speechSynthesis" in window) {
    activeUtterance = null;
    responsePending = false;
    window.speechSynthesis.cancel();
    setOrbState(null);
    microphoneEnabled = false;
    voiceInputButton.setAttribute("aria-pressed", "false");
    stopRecognition();
  }
  setVoiceStatus(enabled ? "Voz activada: respuestas habladas en español de Colombia." : "Voz desactivada. Activa el micrófono para escuchar las respuestas.");
  if (enabled && announce) {
    if ("speechSynthesis" in window && "SpeechSynthesisUtterance" in window) {
      speakResponse("¿En qué puedo ayudarte hoy?");
    } else {
      setVoiceStatus("Este navegador no tiene disponible la lectura de voz.");
    }
  }
}

function speakResponse(text) {
  if (!microphoneEnabled || !voiceOutputEnabled || !("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) return;
  responsePending = true;
  stopRecognition();
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  activeUtterance = utterance;
  utterance.rate = 0.96;
  utterance.pitch = 0.86;
  const pickVoice = () => {
    const voices = window.speechSynthesis.getVoices();
    const spanishVoices = voices.filter((voice) => /^es(?:-|$)/i.test(voice.lang));
    const maleName = /(pablo|jorge|diego|carlos|andrés|andres|juan|miguel|raul|raúl|roberto|antonio|manolo)/i;
    return spanishVoices.find((voice) => /es-CO/i.test(voice.lang) && maleName.test(voice.name)) ||
      spanishVoices.find((voice) => /pablo/i.test(voice.name)) ||
      spanishVoices.find((voice) => maleName.test(voice.name)) ||
      spanishVoices.find((voice) => /es-CO/i.test(voice.lang)) ||
      spanishVoices[0];
  };
  const preferred = pickVoice();
  utterance.lang = preferred?.lang || "es-CO";
  if (preferred) utterance.voice = preferred;
  else window.speechSynthesis.onvoiceschanged = () => { const v = pickVoice(); if (v) utterance.voice = v; };
  utterance.onstart = () => setOrbState("is-speaking");
  utterance.onend = () => {
    if (activeUtterance !== utterance) return;
    activeUtterance = null;
    setOrbState(null);
    window.speechSynthesis.onvoiceschanged = null;
    responsePending = false;
    resumeRecognition();
  };
  utterance.onerror = (event) => {
    if (activeUtterance !== utterance || event.error === "canceled" || event.error === "interrupted") return;
    activeUtterance = null;
    setOrbState(null);
    window.speechSynthesis.onvoiceschanged = null;
    setVoiceStatus(`No pude reproducir la voz (${event.error || "error de audio"}). Revisa el volumen y la salida de audio de Chrome.`);
    responsePending = false;
    resumeRecognition();
  };
  window.speechSynthesis.speak(utterance);
}

// Precargar el listado de voces (Chrome lo llena de forma asíncrona).
if ("speechSynthesis" in window) window.speechSynthesis.getVoices();

voiceToggleButton.addEventListener("click", () => voiceInputButton.click());
setVoiceOutput(voiceOutputEnabled);

if (SpeechRecognition) {
  recognition = new SpeechRecognition();
  recognition.lang = "es-CO";
  recognition.continuous = true;
  recognition.interimResults = false;
  recognition.onstart = () => {
    recognitionRunning = true;
    recognitionSubmitted = false;
    voiceInputButton.setAttribute("aria-pressed", "true");
    setOrbState("is-listening");
    setVoiceStatus("Escuchando… habla ahora.");
  };
  recognition.onresult = (event) => {
    const spoken = Array.from(event.results).filter((result) => result.isFinal).map((result) => result[0].transcript).join(" ").trim().slice(0, 300);
    if (!spoken || recognitionSubmitted) return;
    recognitionSubmitted = true;
    setVoiceStatus("Te escuché. Enviando tu consulta…");
    responsePending = true;
    stopRecognition();
    void submitQuestion(spoken);
  };
  recognition.onerror = (event) => {
    if (event.error === "not-allowed" || event.error === "service-not-allowed") microphoneEnabled = false;
    setOrbState(microphoneEnabled ? "is-listening" : null);
    const messages = {
      "not-allowed": "Chrome bloqueó el micrófono. Permite el acceso en el candado de la barra de direcciones y vuelve a activarlo.",
      "service-not-allowed": "Chrome no permitió usar el reconocimiento de voz en esta página.",
      "no-speech": "No alcancé a oírte. Sigo atento; intenta hablar un poco más cerca del micrófono.",
      "audio-capture": "No encuentro un micrófono disponible. Revisa el dispositivo de entrada de Chrome.",
      network: "El reconocimiento de voz necesita conexión a Internet en este navegador. Puedes escribir tu pregunta."
    };
    setVoiceStatus(messages[event.error] || "No pude reconocer esa frase; sigo activo para intentarlo otra vez.");
  };
  recognition.onend = () => {
    recognitionRunning = false;
    voiceInputButton.setAttribute("aria-pressed", String(microphoneEnabled));
    if (microphoneEnabled && !responsePending && !window.speechSynthesis?.speaking) window.setTimeout(startRecognition, 250);
    else if (!window.speechSynthesis?.speaking) setOrbState(null);
  };
  voiceInputButton.addEventListener("click", () => {
    microphoneEnabled = !microphoneEnabled;
    voiceInputButton.setAttribute("aria-pressed", String(microphoneEnabled));
    voiceInputButton.setAttribute("aria-label", microphoneEnabled ? "Desactivar micrófono" : "Activar micrófono para hablar con NEXUS");
    voiceToggleButton.setAttribute("aria-pressed", String(microphoneEnabled));
    if (microphoneEnabled) {
      setVoiceOutput(true);
      setVoiceStatus("Micrófono activo. Te escucho después del saludo.");
      speakResponse("¿En qué puedo ayudarte hoy?");
      if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) startRecognition();
    } else {
      stopRecognition();
      setVoiceOutput(false);
      if (window.speechSynthesis?.speaking) window.speechSynthesis.cancel();
      setOrbState(null);
      setVoiceStatus("Micrófono desactivado.");
    }
  });
} else {
  voiceInputButton.disabled = true;
  voiceInputButton.title = "El dictado no está disponible en este navegador";
  setVoiceStatus("Este navegador no ofrece dictado de voz; puedes escribir. La lectura en voz alta puede seguir disponible.");
}

function startRecognition() {
  if (!recognition || !microphoneEnabled || recognitionRunning || window.speechSynthesis?.speaking) return;
  try { recognition.start(); } catch { /* El reconocimiento ya está iniciándose; onend lo reintentará si hace falta. */ }
}

function stopRecognition() {
  if (!recognition || !recognitionRunning) return;
  try { recognition.stop(); } catch { /* Puede haberse detenido entre eventos. */ }
}

function resumeRecognition() {
  if (microphoneEnabled) window.setTimeout(startRecognition, 250);
}

function addMessage(text, sender) {
  const message = document.createElement("div");
  message.className = `chat-message ${sender === "user" ? "user-message" : "bot-message"}`;
  message.textContent = text;
  chatMessages.append(message);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function localReply(message) {
  const text = message.toLocaleLowerCase("es");
  if (/^(hola|holi|buenos d[ií]as|buenas tardes|buenas noches|quiubo|qu[eé] m[aá]s)[!. ]*$/i.test(text)) return "¡Hola! Qué gusto saludarte. Soy Extremo NEXUS. Puedes preguntarme por productos, precios, el carrito o cómo crear una solicitud de compra.";
  if (/\b(t[uú] qu[eé] eres|qui[eé]n eres|c[oó]mo te llamas)\b/.test(text)) return "Soy Extremo NEXUS, el asistente de esta tienda académica. Te ayudo a explorar productos, revisar cotizaciones y entender las solicitudes de compra.";
  if (/compr|carrito|solicitud|pedido/.test(text)) return "Añade productos al carrito y elige «Crear solicitud». Es una simulación: no hay pagos ni pedidos a tiendas.";
  if (/aprob|rechaz|revisión|revision|estado/.test(text)) return "Las solicitudes quedan pendientes hasta que una persona revisora las apruebe o rechace en el panel.";
  if (/precio|cotiz|cuesta|valor/.test(text)) return "Los valores son referencias de la fecha indicada en cada ficha, no cotizaciones en tiempo real. Consulta la tienda enlazada.";
  if (/catálogo|catalogo|producto|equipo|hardware|tablet|computador|celular/.test(text)) return "Busca por nombre o filtra el catálogo por categoría. Las fichas enlazan a una fuente cuando se dispone de ella.";
  return `Te escuché decir: «${message.trim()}». Puedo ayudarte con el catálogo, las características y precios de referencia, el carrito, las cotizaciones o las solicitudes de compra. ¿Qué quieres consultar?`;
}

async function answer(message) {
  const host = window.location.hostname || "127.0.0.1";
  try {
    const apiOrigin = window.location.protocol === "https:" ? `${window.location.protocol}//${host}:5443` : `http://${host}:5000`;
    const response = await fetch(`${apiOrigin}/api/assistant`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      credentials: "include", body: JSON.stringify({ message })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Asistente no disponible");
    const reply = typeof result.answer === "string" ? result.answer.trim() : "";
    if (!reply || reply.startsWith("Puedo ayudarte con precios, cotizaciones")) return localReply(message);
    return reply;
  } catch {
    return `${localReply(message)} (respuesta local de respaldo; backend no disponible).`;
  }
}

async function submitQuestion(text) {
  const question = String(text || "").trim().slice(0, 300);
  if (!question) return;
  addMessage(question, "user");
  setOrbState("is-thinking");
  const waiting = document.createElement("div");
  waiting.className = "chat-message bot-message chat-thinking";
  waiting.textContent = "NEXUS está pensando…";
  chatMessages.append(waiting);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  try {
    const response = await answer(question);
    waiting.remove();
    addMessage(response, "bot");
    setVoiceStatus(microphoneEnabled ? "Respuesta lista. Te escucho cuando termine de hablar." : voiceOutputEnabled ? "Respuesta lista." : "Respuesta escrita. Activa el micrófono para escucharla.");
    speakResponse(response);
  } catch {
    waiting.remove();
    const response = localReply(question);
    addMessage(response, "bot");
    setVoiceStatus("Te respondí con la ayuda local. Puedes seguir preguntándome.");
    speakResponse(response);
  } finally {
    if (!window.speechSynthesis?.speaking && !responsePending) setOrbState(null);
  }
}

chatLauncher.addEventListener("click", () => {
  const opening = chatPanel.hidden;
  chatPanel.hidden = !opening;
  chatLauncher.setAttribute("aria-expanded", String(opening));
  if (opening) {
    chatInput.focus();
    // Saludo de bienvenida con voz propia la primera vez que se abre.
    if (!chatLauncher.dataset.greeted) {
      chatLauncher.dataset.greeted = "true";
      speakResponse("¡Hola! Soy Extremo NEXUS, tu copiloto de compras. Pregúntame por catálogo, cotizaciones o códigos de compra.");
    }
  }
});

document.querySelector(".chat-close").addEventListener("click", () => {
  chatPanel.hidden = true;
  chatLauncher.setAttribute("aria-expanded", "false");
  chatLauncher.focus();
});

document.querySelector(".chat-minimize").addEventListener("click", () => {
  chatPanel.hidden = true;
  chatLauncher.setAttribute("aria-expanded", "false");
});

document.querySelector(".chat-expand").addEventListener("click", (event) => {
  const expanded = chatPanel.classList.toggle("chat-panel-expanded");
  event.currentTarget.setAttribute("aria-label", expanded ? "Restaurar tamaño del chat" : "Ampliar chat");
  event.currentTarget.textContent = expanded ? "▢" : "□";
});

document.querySelector("#chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;
  chatInput.value = "";
  await submitQuestion(message);
});

document.querySelectorAll(".chat-suggestions button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelector(".chat-suggestions")?.remove();
    void submitQuestion(button.textContent.trim());
  });
});

// Marca de arranque del asistente (usada por las pruebas automatizadas).
window.NEXUS_ASSISTANT_READY = true;
