import { cn } from '@/lib/utils'
import { Geist } from 'next/font/google';
import { TextReveal } from '@/components/ui/text-reveal'

const geist = Geist({
  subsets: ['latin'],
  variable: '--font-geist',
  weight: '400',
});

const page = () => {
  return (
    <div className='flex w-screen h-screen justify-center'>
      <TextReveal
        className={cn(
          `bg-primary from-foreground to-primary via-rose-200 bg-clip-text text-6xl font-bold text-transparent dark:bg-gradient-to-b`,
          geist.className,
        )}
        from="bottom"
        split="letter"
      >
        Welcome to Advent!
      </TextReveal>
    </div>
  )
}

export default page