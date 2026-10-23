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
 * Kiểm tra trạng thái đang lắng nghe
 */
export function isListening(): boolean {
  return isListeningState;
}
