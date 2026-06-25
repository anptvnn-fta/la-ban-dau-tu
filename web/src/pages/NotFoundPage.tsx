import { Link } from 'react-router-dom'
import { VI } from '@/strings/vi'

export default function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <p className="font-heading text-5xl font-bold text-primary">404</p>
      <p className="mt-2 text-sm text-muted-foreground">{VI.notFound.title}</p>
      <Link to="/" className="mt-4 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90">
        {VI.notFound.backHome}
      </Link>
    </div>
  )
}
