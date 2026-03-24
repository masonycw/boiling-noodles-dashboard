// 全系統統一照片壓縮工具（A3 定義）
export async function compressImage(file, options = {}) {
  const {
    maxWidth = 1200,
    maxHeight = 1200,
    quality = 0.82,
    maxSizeKB = 500,
  } = options

  return new Promise((resolve, reject) => {
    const img = new Image()
    const url = URL.createObjectURL(file)

    img.onload = () => {
      URL.revokeObjectURL(url)

      let { width, height } = img
      if (width > maxWidth || height > maxHeight) {
        const ratio = Math.min(maxWidth / width, maxHeight / height)
        width = Math.round(width * ratio)
        height = Math.round(height * ratio)
      }

      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      canvas.getContext('2d').drawImage(img, 0, 0, width, height)

      const tryCompress = (q) => {
        canvas.toBlob(
          (blob) => {
            if (!blob) return reject(new Error('Compression failed'))
            const sizeKB = blob.size / 1024
            if (sizeKB > maxSizeKB && q > 0.6) {
              tryCompress(Math.max(q - 0.1, 0.6))
            } else {
              const compressed = new File([blob], file.name.replace(/\.[^.]+$/, '.jpg'), {
                type: 'image/jpeg',
                lastModified: Date.now(),
              })
              resolve(compressed)
            }
          },
          'image/jpeg',
          q
        )
      }

      tryCompress(quality)
    }

    img.onerror = reject
    img.src = url
  })
}
