import { cn } from '@/lib/utils'
import { TextReveal } from '@/components/ui/text-reveal'
import { SignedIn, SignedOut } from '@clerk/nextjs'

const page = () => {
  return (
    <div className='flex flex-col w-screen h-screen items-center justify-center gap-8'>
      <TextReveal
        className={cn(`bg-primary from-foreground to-primary via-rose-200 bg-clip-text text-6xl font-bold text-transparent dark:bg-gradient-to-b`)}
        from="bottom"
        split="letter"
      >
        Welcome to Advent!
      </TextReveal>

      <SignedOut>
        <div className="text-center space-y-4">
          <p className="text-lg text-muted-foreground">
            Please sign in to access your dashboard
          </p>
        </div>
      </SignedOut>

      <SignedIn>
        <div className="text-center space-y-4">
          <p className="text-lg text-green-600 dark:text-green-400">
            ✅ You are successfully signed in!
          </p>
          <p className="text-muted-foreground">
            You can now access all features of the application.
          </p>
        </div>
      </SignedIn>
    </div>
  )
}

export default page