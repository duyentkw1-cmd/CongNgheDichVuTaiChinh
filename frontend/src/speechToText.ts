/**
 * speechToText.ts - Module nhận diện giọng nói tiếng Việt bằng Web Speech API
 */

// Polyfill / Safe access to Web Speech API
const SpeechRecognitionClass: any =
  typeof window !== 'undefined'
    ? (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    : null;

export const isSpeechSupported = (): boolean => Boolean(SpeechRecognitionClass);

let recognitionInstance: any = null;
let isListeningState = false;

/**
 * Bắt đầu kích hoạt micro và nhận diện giọng nói tiếng Việt
 * @param onResult Callback nhận kết quả: (transcript: string, isFinal: boolean) => void
 * @param onError Callback khi có lỗi: (error: Error | any) => void
 * @param onEnd Callback kích hoạt khi mic tự động tắt (ngừng nói) hoặc kết thúc
 */
export function startListening(
  onResult: (transcript: string, isFinal: boolean) => void,
  onError?: (error: Error | any) => void,
  onEnd?: () => void
): void {
  if (!isSpeechSupported()) {
    const err = new Error('Trình duyệt hiện tại không hỗ trợ Web Speech API. Vui lòng sử dụng Chrome, Edge hoặc Cốc Cốc.');
    if (onError) onError(err);
    return;
  }

  stopListening();

  try {
    recognitionInstance = new SpeechRecognitionClass();
    recognitionInstance.lang = 'vi-VN';
    recognitionInstance.continuous = false;
    recognitionInstance.interimResults = true;
    recognitionInstance.maxAlternatives = 1;

    recognitionInstance.onresult = (event: any) => {
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

    recognitionInstance.onerror = (event: any) => {
      isListeningState = false;
      if (onError) onError(event);
    };

    recognitionInstance.onend = () => {
      isListeningState = false;
      if (onEnd) onEnd();
    };

    recognitionInstance.start();
    isListeningState = true;
  } catch (error) {
    isListeningState = false;
    if (onError) onError(error);
  }
}

/**
 * Chủ động dừng lắng nghe thủ công
 */
export function stopListening(): void {
  if (recognitionInstance && isListeningState) {
    try {
      recognitionInstance.stop();
    } catch {
      // Bỏ qua nếu đã ngắt
    }
    isListeningState = false;
  }
}

/**
 * Phát âm thanh tiếng Việt tự nhiên (TTS)
 * Ưu tiên âm thanh Google Translate TTS tiếng Việt chuẩn (chị Google).
 * Nếu offline, chỉ dùng Web Speech API khi THỰC SỰ có voice tiếng Việt (tránh phát âm sai bằng giọng tiếng Anh).
 */
export function speakVietnamese(text: string, onEnd?: () => void): void {
  if (typeof window === 'undefined') {
    if (onEnd) onEnd();
    return;
  }

  let hasEnded = false;
  const finish = () => {
    if (!hasEnded) {
      hasEnded = true;
      if (onEnd) onEnd();
    }
  };

  // Timeout bảo vệ: nếu TTS không phản hồi sau 6 giây, gọi finish() luôn
  const safetyTimer = setTimeout(() => {
    console.warn('TTS timeout - gọi callback bảo vệ');
    finish();
  }, 6000);

  const safeFinish = () => {
    clearTimeout(safetyTimer);
    finish();
  };

  // 1. Dùng giọng đọc tiếng Việt chuẩn Google TTS (tự nhiên 100%, không bị giọng Mỹ đọc tiếng Việt)
  try {
    const encoded = encodeURIComponent(text);
    const audioUrl = `https://translate.google.com/translate_tts?ie=UTF-8&q=${encoded}&tl=vi&client=tw-ob`;
    const audio = new Audio(audioUrl);

    audio.onended = safeFinish;
    audio.onerror = () => {
      fallbackSpeechSynthesis(text, safeFinish);
    };

    // Timeout riêng cho load audio: nếu không load được trong 3 giây, bỏ qua Google TTS
    const loadTimer = setTimeout(() => {
      audio.pause();
      audio.src = '';
      fallbackSpeechSynthesis(text, safeFinish);
    }, 3000);

    audio.oncanplaythrough = () => clearTimeout(loadTimer);

    const playPromise = audio.play();
    if (playPromise !== undefined) {
      playPromise.catch(() => {
        clearTimeout(loadTimer);
        fallbackSpeechSynthesis(text, safeFinish);
      });
    }
    return;
  } catch {
    fallbackSpeechSynthesis(text, safeFinish);
  }
}

function fallbackSpeechSynthesis(text: string, onFinish: () => void): void {
  if (!window.speechSynthesis) {
    onFinish();
    return;
  }
  window.speechSynthesis.cancel();
  const voices = window.speechSynthesis.getVoices();
  const viVoice = voices.find(v =>
    v.lang === 'vi-VN' ||
    v.lang === 'vi_VN' ||
    v.lang.toLowerCase().startsWith('vi') ||
    /vietnam|hoaimy|namminh/i.test(v.name)
  );

  // QUAN TRỌNG: Chỉ đọc bằng SpeechSynthesis nếu THỰC SỰ có voice tiếng Việt!
  // Tuyệt đối không để Microsoft David (English) đọc tiếng Việt vì sẽ phát âm sai thành tiếng Anh!
  if (!viVoice) {
    console.warn("Máy chưa có voice tiếng Việt của Windows. Không đọc giọng tiếng Anh để tránh phát âm sai.");
    onFinish();
    return;
  }

  const u = new SpeechSynthesisUtterance(text);
  u.voice = viVoice;
  u.lang = 'vi-VN';
  u.rate = 1.0;
  u.onend = onFinish;
  u.onerror = onFinish;
  window.speechSynthesis.speak(u);
}
