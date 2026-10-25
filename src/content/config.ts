import { glob } from "astro/loaders";
import { defineCollection, z } from "astro:content";

const postsCollection = defineCollection({
	schema: z.object({
		title: z.string(),
		published: z.date(),
		updated: z.date().optional(),
		draft: z.boolean().optional().default(false),
		description: z.string().optional().default(""),
		image: z.string().optional().default(""),
		tags: z.array(z.string()).optional().default([]),
		category: z.string().optional().nullable().default(""),
		lang: z.string().optional().default(""),
		pinned: z.boolean().optional().default(false),

		/* For internal use */
		prevTitle: z.string().default(""),
		prevSlug: z.string().default(""),
		nextTitle: z.string().default(""),
		nextSlug: z.string().default(""),
	}),
});
const specCollection = defineCollection({
	schema: z.object({}),
});
// 论文知识库：由 paper_sync 引擎在人工审核通过后写入（草稿永不进入本目录）
const papersCollection = defineCollection({
	loader: glob({ pattern: "**/*.md", base: "./src/content/papers" }),
	schema: z.object({
		title: z.string(),
		description: z.string().default(""),
		paperId: z.string().optional(),
		year: z.number().int().optional(),
		venue: z.string().optional(),
		doi: z.string().optional(),
		arxiv: z.string().optional(),
		paperUrl: z.string().optional(),
		githubUrl: z.string().optional(),
		topics: z.array(z.string()).default([]),
		tags: z.array(z.string()).default([]),
		draft: z.boolean().default(false),
		updated: z.string().optional(),
	}),
});
export const collections = {
	posts: postsCollection,
	spec: specCollection,
	papers: papersCollection,
};
