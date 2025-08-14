import { cn } from '@/lib/utils'
import { TextReveal } from '@/components/ui/text-reveal'


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
    </div>
  )
}

export default page