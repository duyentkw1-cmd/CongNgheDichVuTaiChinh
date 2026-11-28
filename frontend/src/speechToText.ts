/**
 * speechToText.ts - Module nhận diện giọng nói & đọc nhắc lại tiếng Việt
 */

const SpeechRecognitionClass: any =
  typeof window !== 'undefined'
    ? (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    : null;

export const isSpeechSupported = (): boolean => Boolean(SpeechRecognitionClass);

let recognitionInstance: any = null;
let isListeningState = false;
let listenSilenceTimer: number | null = null;

function clearListenSilenceTimer(): void {
  if (listenSilenceTimer !== null && typeof window !== 'undefined') {
    window.clearTimeout(listenSilenceTimer);
    listenSilenceTimer = null;
  }
}

let activeSpeakId = 0;
let activeAudio: HTMLAudioElement | null = null;
let activeTimers: number[] = [];

function clearSpeechTimers(): void {
  for (const id of activeTimers) {
    window.clearTimeout(id);
  }
  activeTimers = [];
}

/**
 * Dừng phát âm thanh nhắc lại hiện tại (nếu có) và hủy callback chờ.
 */
export function stopSpeaking(): void {
  if (typeof window === 'undefined') return;
  activeSpeakId += 1;
  clearSpeechTimers();

  if (activeAudio) {
    try {
      activeAudio.onended = null;
      activeAudio.onerror = null;
      activeAudio.onplaying = null;
      activeAudio.oncanplaythrough = null;
      activeAudio.pause();
      activeAudio.src = '';
    } catch {
      // Bỏ qua lỗi khi giải phóng audio
    }
    activeAudio = null;
  }

  if (window.speechSynthesis) {
    try {
      window.speechSynthesis.cancel();
    } catch {
      // Bỏ qua
    }
  }
}

export type ListenOptions = {
  continuous?: boolean;
  silenceMs?: number;
};

/**
 * Bắt đầu kích hoạt micro và nhận diện giọng nói tiếng Việt
 */
export function startListening(
  onResult: (transcript: string, isFinal: boolean) => void,
  onError?: (error: Error | any) => void,
  onEnd?: () => void,
  options?: ListenOptions
): void {
  if (!isSpeechSupported()) {
    const err = new Error('Trình duyệt hiện tại không hỗ trợ Web Speech API. Vui lòng sử dụng Chrome, Edge hoặc Cốc Cốc.');
    if (onError) onError(err);
    return;
  }

  stopListening();

  const continuous = Boolean(options?.continuous);
  const silenceMs = options?.silenceMs ?? 1800;

  try {
    const instance = new SpeechRecognitionClass();
    recognitionInstance = instance;
    instance.lang = 'vi-VN';
    instance.continuous = continuous;
    instance.interimResults = true;
    instance.maxAlternatives = 1;

    let latestFullText = '';

    instance.onresult = (event: any) => {
      if (recognitionInstance !== instance) return;

      if (continuous) {
        const parts: string[] = [];
        for (let i = 0; i < event.results.length; ++i) {
          const text = (event.results[i][0]?.transcript || '').trim();
          if (text) parts.push(text);
        }
        const currentText = parts.join(' ').replace(/\s+/g, ' ').trim();
        if (!currentText) return;
        latestFullText = currentText;
        onResult(currentText, false);
        clearListenSilenceTimer();
        listenSilenceTimer = window.setTimeout(() => {
          if (recognitionInstance !== instance) return;
          stopListening();
          onResult(latestFullText, true);
        }, silenceMs);
        return;
      }

      let interimTranscript = '';
      let finalTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const item = event.results[i];
        const text = item[0]?.transcript || '';
        if (item.isFinal) {
          finalTranscript += text;
        } else {
          interimTranscript += text;
        }
      }

      const currentText = (finalTranscript || interimTranscript).trim();
      const isFinal = Boolean(finalTranscript);

      if (currentText) {
        onResult(currentText, isFinal);
      }
    };

    instance.onerror = (event: any) => {
      if (recognitionInstance !== instance) return;
      clearListenSilenceTimer();
      isListeningState = false;
      recognitionInstance = null;
      if (onError) onError(event);
    };

    instance.onend = () => {
      if (recognitionInstance !== instance) return;
      clearListenSilenceTimer();
      isListeningState = false;
      recognitionInstance = null;
      if (onEnd) onEnd();
    };

    instance.start();
    isListeningState = true;
  } catch (error) {
    clearListenSilenceTimer();
    isListeningState = false;
    recognitionInstance = null;
    if (onError) onError(error);
  }
}

/**
 * Chủ động dừng lắng nghe thủ công
 */
export function stopListening(): void {
  clearListenSilenceTimer();
  const current = recognitionInstance;
  recognitionInstance = null;
  isListeningState = false;
  if (current) {
    try {
      current.onresult = null;
      current.onerror = null;
      current.onend = null;
      current.stop();
    } catch {
      // Bỏ qua nếu đã ngắt
    }
  }
}

function getVietnameseVoice(): SpeechSynthesisVoice | undefined {
  if (typeof window === 'undefined' || !window.speechSynthesis) return undefined;
  const voices = window.speechSynthesis.getVoices();
  return voices.find(
    (v) =>
      v.lang === 'vi-VN' ||
      v.lang === 'vi_VN' ||
      v.lang.toLowerCase().startsWith('vi') ||
      /vietnam|hoaimy|namminh/i.test(v.name)
  );
}

/**
 * Phát âm thanh tiếng Việt tự nhiên (TTS)
 * - Ưu tiên voice tiếng Việt có sẵn trên trình duyệt/hệ điều hành (offline, riêng tư) nếu có,
 *   hoặc Google Translate TTS nếu máy chưa cài gói giọng tiếng Việt.
 * - Tuyệt đối không dùng giọng tiếng Anh đọc tiếng Việt.
 */
export function speakVietnamese(text: string, onEnd?: () => void): void {
  if (typeof window === 'undefined' || !text.trim()) {
    if (onEnd) onEnd();
    return;
  }

  stopSpeaking();
  const speakId = activeSpeakId;

  let hasEnded = false;
  const finish = () => {
    if (speakId !== activeSpeakId || hasEnded) return;
    hasEnded = true;
    clearSpeechTimers();
    activeAudio = null;
    if (onEnd) onEnd();
  };

  const maxPlaybackMs = Math.max(9000, text.length * 160);

  // Nếu máy có sẵn voice tiếng Việt chất lượng (ví dụ Edge HoaiMy / Chrome Google Tiếng Việt), dùng local trước
  const localViVoice = getVietnameseVoice();
  if (localViVoice) {
    fallbackSpeechSynthesis(text, speakId, maxPlaybackMs, finish, localViVoice);
    return;
  }

  // Nếu Google TTS vượt quá 200 ký tự, ưu tiên SpeechSynthesis hoặc rút gọn an toàn
  if (text.length > 190) {
    fallbackSpeechSynthesis(text, speakId, maxPlaybackMs, finish);
    return;
  }

  try {
    const encoded = encodeURIComponent(text);
    const audioUrl = `https://translate.google.com/translate_tts?ie=UTF-8&q=${encoded}&tl=vi&client=tw-ob`;
    const audio = new Audio(audioUrl);
    activeAudio = audio;

    let playbackTimerStarted = false;
    const startPlaybackTimeout = () => {
      if (playbackTimerStarted || speakId !== activeSpeakId) return;
      playbackTimerStarted = true;
      const t = window.setTimeout(() => {
        console.warn('TTS playback timeout - gọi callback bảo vệ');
        if (activeAudio === audio) {
          try {
            audio.pause();
            audio.src = '';
          } catch {
            // Bỏ qua
          }
        }
        finish();
      }, maxPlaybackMs);
      activeTimers.push(t);
    };

    const loadTimer = window.setTimeout(() => {
      if (speakId !== activeSpeakId) return;
      try {
        audio.onended = null;
        audio.onerror = null;
        audio.pause();
        audio.src = '';
      } catch {
        // Bỏ qua
      }
      if (activeAudio === audio) activeAudio = null;
      fallbackSpeechSynthesis(text, speakId, maxPlaybackMs, finish);
    }, 3000);
    activeTimers.push(loadTimer);

    const handleFallback = () => {
      window.clearTimeout(loadTimer);
      if (speakId !== activeSpeakId) return;
      if (activeAudio === audio) activeAudio = null;
      fallbackSpeechSynthesis(text, speakId, maxPlaybackMs, finish);
    };

    audio.onended = () => {
      window.clearTimeout(loadTimer);
      finish();
    };
    audio.onerror = handleFallback;
    audio.oncanplaythrough = () => {
      window.clearTimeout(loadTimer);
      startPlaybackTimeout();
    };
    audio.onplaying = () => {
      window.clearTimeout(loadTimer);
      startPlaybackTimeout();
    };

    const playPromise = audio.play();
    if (playPromise !== undefined) {
      playPromise.catch(handleFallback);
    }
  } catch {
    fallbackSpeechSynthesis(text, speakId, maxPlaybackMs, finish);
  }
}

function fallbackSpeechSynthesis(
  text: string,
  speakId: number,
  maxPlaybackMs: number,
  onFinish: () => void,
  preselectedVoice?: SpeechSynthesisVoice
): void {
  if (speakId !== activeSpeakId) return;
  if (!window.speechSynthesis) {
    onFinish();
    return;
  }

  window.speechSynthesis.cancel();
  const viVoice = preselectedVoice || getVietnameseVoice();

  // Chỉ đọc bằng SpeechSynthesis nếu thực sự có voice tiếng Việt
  if (!viVoice) {
    console.warn('Máy chưa có voice tiếng Việt của Windows. Không đọc giọng tiếng Anh để tránh phát âm sai.');
    onFinish();
    return;
  }

  const safetyTimer = window.setTimeout(() => {
    if (speakId !== activeSpeakId) return;
    try {
      window.speechSynthesis.cancel();
    } catch {
      // Bỏ qua
    }
    onFinish();
  }, maxPlaybackMs);
  activeTimers.push(safetyTimer);

  const u = new SpeechSynthesisUtterance(text);
  u.voice = viVoice;
  u.lang = 'vi-VN';
  u.rate = 1.0;
  u.onend = () => {
    window.clearTimeout(safetyTimer);
    onFinish();
  };
  u.onerror = () => {
    window.clearTimeout(safetyTimer);
    onFinish();
  };
  window.speechSynthesis.speak(u);
}
