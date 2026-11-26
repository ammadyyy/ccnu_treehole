import { useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import { TAGS } from '../lib/types'
import Button from '../components/ui/Button'

const TITLE_MAX = 50
const BODY_MAX = 2000
const CAPTION_MAX = 100
const MAX_IMAGES = 3
const MAX_IMAGE_BYTES = 5 * 1024 * 1024

interface PendingImage {
  file: File
  previewUrl: string
  caption: string
}

const URL_PATTERN = /(https?:\/\/|www\.|[\w-]+\.(com|cn|net|org|edu|io|app|site|xyz))/i

export default function NewPost() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [images, setImages] = useState<PendingImage[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  if (!user?.currentMask) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-8 text-center">
        <p className="text-gray-700">发帖前需要先领取并选择一个面具</p>
        <Link to="/me/masks" className="mt-3 inline-block text-sm text-gray-900 underline">
          前往「我的面具」
        </Link>
      </div>
    )
  }

  const toggleTag = (t: string) => {
    if (tags.includes(t)) {
      setTags(tags.filter((x) => x !== t))
    } else if (tags.length < 2) {
      setTags([...tags, t])
    }
  }

  const onSelectImages = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    const remaining = MAX_IMAGES - images.length
    const accepted: PendingImage[] = []
    for (const f of files.slice(0, remaining)) {
      if (!f.type.startsWith('image/')) continue
      if (f.size > MAX_IMAGE_BYTES) continue
      accepted.push({ file: f, previewUrl: URL.createObjectURL(f), caption: '' })
    }
    if (accepted.length < files.length) {
      setError(`最多 ${MAX_IMAGES} 张图片，且单张不超过 5MB，已忽略不符合的文件`)
    } else {
      setError('')
    }
    setImages((prev) => [...prev, ...accepted])
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const removeImage = (idx: number) => {
    setImages((prev) => {
      const next = prev.filter((_, i) => i !== idx)
      return next
    })
  }

  const setCaption = (idx: number, caption: string) => {
    setImages((prev) => prev.map((img, i) => (i === idx ? { ...img, caption } : img)))
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')

    if (!title.trim()) return setError('标题不能为空')
    if (title.trim().length > TITLE_MAX) return setError(`标题最多 ${TITLE_MAX} 字`)
    if (title.includes('\n')) return setError('标题不能包含换行')
    if (!body.trim()) return setError('正文不能为空')
    if (body.trim().length > BODY_MAX) return setError(`正文最多 ${BODY_MAX} 字`)
    if (tags.length < 1 || tags.length > 2) return setError('请选择 1–2 个标签')
    for (const img of images) {
      if (img.caption.trim().length > CAPTION_MAX) return setError(`图片说明最多 ${CAPTION_MAX} 字`)
      if (URL_PATTERN.test(img.caption)) return setError('图片说明中不允许填写网址')
    }

    const fd = new FormData()
    fd.append('title', title.trim())
    fd.append('body', body)
    fd.append('tags', JSON.stringify(tags))
    fd.append('captions', JSON.stringify(images.map((i) => i.caption.trim())))
    for (const img of images) fd.append('images', img.file)

    setLoading(true)
    try {
      const res = await api.upload<{ post: { id: number } }>('/posts', fd)
      navigate(`/post/${res.post.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '发布失败，请稍后再试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="text-xl font-bold text-gray-900">写树洞</h1>
      <p className="mt-1 text-xs text-gray-400">以「{user.currentMask.token}」身份发布</p>

      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <div>
          <label htmlFor="title" className="block text-sm font-medium text-gray-700">
            标题
          </label>
          <input
            id="title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
            placeholder="一句话标题"
          />
          <div className="mt-1 text-right text-xs text-gray-400">
            {title.length}/{TITLE_MAX}
          </div>
        </div>

        <div>
          <label htmlFor="body" className="block text-sm font-medium text-gray-700">
            正文
          </label>
          <textarea
            id="body"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={8}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
            placeholder="写下你想说的话……"
          />
          <div className="mt-1 text-right text-xs text-gray-400">
            {body.length}/{BODY_MAX}
          </div>
        </div>

        <div>
          <span className="block text-sm font-medium text-gray-700">标签（选 1–2 个）</span>
          <div className="mt-2 flex flex-wrap gap-2">
            {TAGS.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => toggleTag(t)}
                className={`rounded-full px-3 py-1 text-sm ${
                  tags.includes(t)
                    ? 'bg-gray-900 text-white'
                    : 'bg-white text-gray-600 hover:bg-gray-100'
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        <div>
          <span className="block text-sm font-medium text-gray-700">图片（最多 3 张，每张 ≤5MB）</span>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            multiple
            onChange={onSelectImages}
            className="mt-2 block text-sm text-gray-500"
          />
          {images.length > 0 && (
            <ul className="mt-3 space-y-3">
              {images.map((img, idx) => (
                <li key={idx} className="flex gap-3 rounded-lg border border-gray-200 p-3">
                  <img
                    src={img.previewUrl}
                    alt={`图片 ${idx + 1}`}
                    className="h-20 w-20 rounded object-cover"
                  />
                  <div className="flex-1">
                    <input
                      type="text"
                      value={img.caption}
                      onChange={(e) => setCaption(idx, e.target.value)}
                      placeholder="图片说明（可选，≤100 字）"
                      className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-gray-500 focus:outline-none"
                    />
                    <div className="mt-1 flex items-center justify-between">
                      <span className="text-xs text-gray-400">
                        {img.caption.length}/{CAPTION_MAX}
                      </span>
                      <button
                        type="button"
                        onClick={() => removeImage(idx)}
                        className="text-xs text-red-600 hover:underline"
                      >
                        移除
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

        <Button type="submit" loading={loading} disabled={loading}>
          发布
        </Button>
      </form>
    </div>
  )
}
