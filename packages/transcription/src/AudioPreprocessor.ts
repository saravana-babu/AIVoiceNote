/**
 * Helper to preprocess raw PCM audio to Log-Mel Spectrogram features
 * required by Whisper models (80 Mel channels, 16kHz sample rate, 512 FFT size, 160 hop size).
 */
export class AudioPreprocessor {
  // Pre-calculated Mel Filterbank weights for 16kHz sample rate, 512 FFT size, 80 Mel bands
  private static melFilters: number[][] = [];

  static initializeMelFilters() {
    if (this.melFilters.length > 0) return;

    const numBands = 80;
    const fftSize = 512;
    const sampleRate = 16000;
    const numBins = Math.floor(fftSize / 2) + 1;

    // Initialize filters array
    const filters = Array.from({ length: numBands }, () => new Array(numBins).fill(0));

    // Convert Hz to Mel
    const hzToMel = (hz: number) => 2595 * Math.log10(1 + hz / 700);
    const melToHz = (mel: number) => 700 * (Math.pow(10, mel / 2595) - 1);

    const minFreq = 0;
    const maxFreq = sampleRate / 2;
    const minMel = hzToMel(minFreq);
    const maxMel = hzToMel(maxFreq);

    // Create band spacing
    const melPoints = Array.from(
      { length: numBands + 2 },
      (_, i) => minMel + (i * (maxMel - minMel)) / (numBands + 1),
    );
    const hzPoints = melPoints.map(melToHz);

    // Map Hz points to FFT bin indices
    const binPoints = hzPoints.map((hz) => Math.floor(((fftSize + 1) * hz) / sampleRate));

    for (let m = 0; m < numBands; m++) {
      const leftBin = binPoints[m];
      const centerBin = binPoints[m + 1];
      const rightBin = binPoints[m + 2];

      for (let k = leftBin; k < centerBin; k++) {
        if (centerBin !== leftBin) {
          filters[m][k] = (k - leftBin) / (centerBin - leftBin);
        }
      }
      for (let k = centerBin; k <= rightBin; k++) {
        if (rightBin !== centerBin) {
          filters[m][k] = (rightBin - k) / (rightBin - centerBin);
        }
      }
    }

    this.melFilters = filters;
  }

  /**
   * Generates Log-Mel Spectrogram features from Float32 PCM audio data.
   * Outputs a 1D float array of size [80 * 3000] (for 30 seconds of audio at 100 frames/sec)
   */
  static getLogMelSpectrogram(pcmData: Float32Array): Float32Array {
    this.initializeMelFilters();

    const numBands = 80;
    const fftSize = 512;
    const windowSize = 400; // 25ms
    const hopSize = 160; // 10ms
    const maxFrames = 3000; // 30 seconds at 100 frames/sec

    const numSamples = pcmData.length;
    // Calculate total possible frames
    const numFrames = Math.max(1, Math.floor((numSamples - windowSize) / hopSize) + 1);
    const resultFrames = Math.min(numFrames, maxFrames);

    // Hanning Window
    const hanningWindow = new Float32Array(windowSize);
    for (let i = 0; i < windowSize; i++) {
      hanningWindow[i] = 0.5 * (1 - Math.cos((2 * Math.PI * i) / (windowSize - 1)));
    }

    // Output flat array initialized to log-mel baseline (-10.0 or typical silence log value)
    // Whisper expects input shape [1, 80, 3000]
    const melSpectrogram = new Float32Array(numBands * maxFrames);
    melSpectrogram.fill(-10.0);

    const real = new Float32Array(fftSize);
    const imag = new Float32Array(fftSize);
    const mag = new Float32Array(Math.floor(fftSize / 2) + 1);

    for (let f = 0; f < resultFrames; f++) {
      const startSample = f * hopSize;

      // 1. Prepare frame and apply Hanning window
      real.fill(0);
      imag.fill(0);
      for (let i = 0; i < windowSize; i++) {
        if (startSample + i < numSamples) {
          real[i] = pcmData[startSample + i] * hanningWindow[i];
        }
      }

      // 2. Simple DFT (Discrete Fourier Transform)
      // Since FFT in pure JS is slow and this runs on audio frames, we compute the DFT bin energies
      const fftBins = mag.length;
      for (let k = 0; k < fftBins; k++) {
        let sumReal = 0;
        let sumImag = 0;
        for (let n = 0; n < windowSize; n++) {
          const angle = (2 * Math.PI * k * n) / fftSize;
          sumReal += real[n] * Math.cos(angle);
          sumImag -= real[n] * Math.sin(angle);
        }
        mag[k] = Math.sqrt(sumReal * sumReal + sumImag * sumImag);
      }

      // 3. Apply Mel Filters
      for (let m = 0; m < numBands; m++) {
        let bandEnergy = 0;
        for (let k = 0; k < fftBins; k++) {
          bandEnergy += mag[k] * this.melFilters[m][k];
        }

        // 4. Log scale calculation
        const logMel = Math.log10(Math.max(bandEnergy, 1e-5));

        // Fill in shape [numBands, maxFrames] flat structure: melSpectrogram[m * maxFrames + f]
        melSpectrogram[m * maxFrames + f] = logMel;
      }
    }

    // Normalize Mel Spectrogram to match Whisper's training inputs
    let maxVal = -Infinity;
    for (let i = 0; i < melSpectrogram.length; i++) {
      if (melSpectrogram[i] > maxVal) {
        maxVal = melSpectrogram[i];
      }
    }

    // Standard normalization scale
    const normShift = maxVal - 8.0;
    for (let i = 0; i < melSpectrogram.length; i++) {
      melSpectrogram[i] = Math.max(-10.0, (melSpectrogram[i] - normShift) / 4.0);
    }

    return melSpectrogram;
  }

  /**
   * Helper to decode standard WAV files and extract raw PCM Float32 array.
   */
  static decodeWavToPcm(wavBuffer: ArrayBuffer): Float32Array {
    const view = new DataView(wavBuffer);

    // Verify RIFF / WAVE headers
    const riff = String.fromCharCode(
      view.getUint8(0),
      view.getUint8(1),
      view.getUint8(2),
      view.getUint8(3),
    );
    const wave = String.fromCharCode(
      view.getUint8(8),
      view.getUint8(9),
      view.getUint8(10),
      view.getUint8(11),
    );

    if (riff !== 'RIFF' || wave !== 'WAVE') {
      throw new Error('Invalid WAV file header');
    }

    // Find fmt chunk to read channel count, sample rate, bit depth
    let offset = 12;
    let numChannels = 1;
    let sampleRate = 16000;
    let bitsPerSample = 16;
    let dataOffset = 0;
    let dataSize = 0;

    while (offset < view.byteLength) {
      const chunkId = String.fromCharCode(
        view.getUint8(offset),
        view.getUint8(offset + 1),
        view.getUint8(offset + 2),
        view.getUint8(offset + 3),
      );
      const chunkSize = view.getUint32(offset + 4, true);

      if (chunkId === 'fmt ') {
        numChannels = view.getUint16(offset + 8, true);
        sampleRate = view.getUint32(offset + 10, true);
        bitsPerSample = view.getUint16(offset + 22, true);
      } else if (chunkId === 'data') {
        dataOffset = offset + 8;
        dataSize = chunkSize;
        break;
      }
      offset += 8 + chunkSize;
    }

    if (dataOffset === 0) {
      throw new Error('WAV data chunk not found');
    }

    const sampleCount = Math.floor(dataSize / (bitsPerSample / 8));
    const pcmData = new Float32Array(sampleCount);

    // Extract Float32 samples from bitsPerSample
    for (let i = 0; i < sampleCount; i++) {
      const fileOffset = dataOffset + i * (bitsPerSample / 8);
      if (fileOffset >= view.byteLength) break;

      let val = 0;
      if (bitsPerSample === 16) {
        val = view.getInt16(fileOffset, true) / 32768.0;
      } else if (bitsPerSample === 8) {
        val = (view.getUint8(fileOffset) - 128) / 128.0;
      } else if (bitsPerSample === 32) {
        val = view.getFloat32(fileOffset, true);
      }
      pcmData[i] = val;
    }

    // Downsample if not 16000Hz, or downmix multi-channel
    if (sampleRate !== 16000 || numChannels > 1) {
      return this.resampleAndDownmix(pcmData, sampleRate, 16000, numChannels);
    }

    return pcmData;
  }

  private static resampleAndDownmix(
    input: Float32Array,
    fromRate: number,
    toRate: number,
    numChannels: number,
  ): Float32Array {
    // 1. Downmix to mono if multi-channel
    let monoPcm = input;
    if (numChannels > 1) {
      const length = Math.floor(input.length / numChannels);
      monoPcm = new Float32Array(length);
      for (let i = 0; i < length; i++) {
        let sum = 0;
        for (let c = 0; c < numChannels; c++) {
          sum += input[i * numChannels + c];
        }
        monoPcm[i] = sum / numChannels;
      }
    }

    // 2. Resample to 16000Hz (linear interpolation)
    if (fromRate === toRate) {
      return monoPcm;
    }

    const ratio = fromRate / toRate;
    const targetLength = Math.floor(monoPcm.length / ratio);
    const output = new Float32Array(targetLength);

    for (let i = 0; i < targetLength; i++) {
      const index = i * ratio;
      const left = Math.floor(index);
      const right = Math.min(monoPcm.length - 1, left + 1);
      const fraction = index - left;
      output[i] = monoPcm[left] * (1 - fraction) + monoPcm[right] * fraction;
    }

    return output;
  }
}
