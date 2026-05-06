# main (1)

# An anti-CD47 antibody binds to a distinct epitope in a novel metal ion-dependent manner to minimize cross-linking of red blood cells

Received for publication, December 29, 2024, and in revised form, May 22, 2025

https://doi.org/10.1016/j.jbc.2025.110420

Xiao Lu $^{1,\ddagger}$ , Ziyue Chen $^{2,\ddagger}$ , Chunyan Yi $^{1,\ddagger}$ , Zhiyang Ling $^{1,\ddagger}$ , Jing Ye $^{3,\ddagger}$ , Kaijian Chen $^{2}$ , Yao Cong $^{2}$ , Wangmo Sonam $^{3}$ , Shipeng Cheng $^{1}$ , Ran Wang $^{4}$ , Danyan Zhang $^{3}$ , Jiefang Xu $^{4}$ , Jichao Yang $^{3}$ , Liyan Ma $^{1}$ , Qing Duan $^{5}$ , Xiaoyu Sun $^{6,*}$ , Jianping Ding $^{2,3,*}$ , and Bing Sun $^{1,3,*}$

From the $^{1}$ Key Laboratory of Multi-Cell Systems, Shanghai Institute of Biochemistry and Cell Biology, Center for Excellence in Molecular Cell Science, University of Chinese Academy of Sciences, Chinese Academy of Sciences, Shanghai, China; $^{2}$ Key Laboratory of RNA Innovation, Science and Engineering, Shanghai Institute of Biochemistry and Cell Biology, Center for Excellence in Molecular Cell Science, University of Chinese Academy of Sciences, Chinese Academy of Sciences, Shanghai, China; $^{3}$ School of Life Science and Technology, ShanghaiTech University, Shanghai, China; $^{4}$ Division of Life Sciences and Medicine, University of Science and Technology of China, Hefei, China; $^{5}$ Research & New Technology Department, BioDlink Biopharm Co., Ltd, Suzhou, China; $^{6}$ Shanghai Institute of Infectious Disease and Biosecurity, Shanghai Medical College, Fudan University, Shanghai, China

Reviewed by members of the JBC Editorial Board. Edited by Paul Shapiro

Cluster of differentiation 47 (CD47) is a widely expressed transmembrane protein that plays a crucial role in immune self-recognition. Cancer cells upregulate CD47 expression to promote immune escape through activating the “don’t eat me” signal via interactions with signal regulatory protein $\alpha$ (SIRP $\alpha$ ) on macrophages. The effectiveness of anti-CD47 antibodies has been demonstrated in multiple tumor models. However, since CD47 is also expressed in human red blood cells (RBCs) and platelets, the clinical application of anti-CD47 antibodies requires careful consideration of blood toxicity. One major obstacle to the clinical application of CD47 antibodies is the hemagglutination caused by RBCs cross-linking. In this study, we generated Hu1C8, a humanized anti-CD47 monoclonal antibody that demonstrated increased selectivity for binding to CD47 on cancer cells and lacked hemagglutination activity. Epitope mapping and the crystal structure of the Hu1C8 Fab-CD47 extracellular domain (ECD) complex revealed that Hu1C8 binds to a distinct epitope of CD47 in a Ca $^{2+}$ -dependent manner. The unique recognition and binding mode allowed Hu1C8 to bind CD47 on RBCs with reduced hemagglutination activity while still maintaining effective antitumor activity. These findings demonstrate a feasible strategy for developing CD47 antibodies with high antitumor activity but low RBC hemagglutination activity. Our study elucidates how epitope-specific antibody influences antibody-induced cell cross-linking, offering innovative strategies for antibody design to either leverage or avoid cell cross-linking effects.

CD47, which is formerly known as integrin-associated protein (IAP) (1), is a cell surface glycoprotein that is ubiquitously expressed on human cells (2, 3). It has been implicated in the regulation of multiple cellular processes involved in immune responses, such as the inhibition of innate immune cells and cell migration (2). SIRPα is the inhibitory receptor of CD47 expressed on myeloid cells (4, 5), including macrophages, dendritic cells (DCs) and neutrophils, and plays a crucial role in the regulation of innate immune responses and phagocytosis (3, 6). The CD47/SIRPα interaction provides a “don’t eat me” signal that inhibits phagocytosis. CD47 has been identified as a tumor antigen that is expressed by multiple human tumor types, including leukemia (7), lymphoma (8), myeloma (9), and certain solid tumors (10–12). Many studies have suggested that the CD47/SIRPα axis acts as an innate immune checkpoint in macrophages (13, 14). Cancer cells overexpress CD47 to evade immune surveillance; thus, CD47 can be a target for immunotherapy (15). Blocking the CD47/SIRPα axis has been shown to enhance phagocytosis of tumor cells in vitro and promote macrophage-mediated tumor elimination in multiple in vivo tumor models (7, 16, 17). These findings suggest that targeting this axis may be a promising approach for cancer immunotherapy. However, CD47 is also expressed on normal cells, particularly on RBCs and platelets; thus, some anti-CD47 antibody therapies have shown significant side effects, including hemagglutination and the phagocytosis of RBCs (18, 19). The on-target off-tumor effects of anti-CD47 antibody therapeutics significantly impact the intended functions of the antibodies. Therefore, the development of anti-CD47 antibodies with minimized RBC binding and toxicity, while retaining potent activity against tumor cells, represents a promising approach for advancing CD47-targeted cancer immunotherapy.

In this study, we generated 1C8, an anti-CD47 antibody with minimal hemagglutination activity, using rabbit single

B-cell screening technology. Following humanization, the resulting antibody was named Hu1C8. Functional studies showed that Hu1C8 exhibited similar activity to other anti-CD47 antibodies in the clinical stage by promoting tumor cell phagocytosis in vitro and exerting antitumor effects in vivo. In addition, Hu1C8 exhibited a reduced risk of RBC toxicity due to its low hemagglutination activity. Structural analysis revealed that Hu1C8 binds to the proximal membrane region of CD47 with a unique binding angle, effectively preventing the antibody arms from simultaneously engaging CD47 on adjacent cells, thus avoiding cell cross-linking. Notably, the binding of Hu1C8 to CD47 depends on $Ca^{2+}$ , which has been rarely reported before.

In conclusion, we have demonstrated the therapeutic potential of the humanized rabbit-derived monoclonal anti-CD47 antibody Hu1C8. Crystal structure analysis revealed the $Ca^{2+}$ -dependent recognition pattern of Hu1C8. This pattern involves a unique binding angle of one Hu1C8 Fab arm to CD47, which restricts the accessibility of the other arm of the antibody, thus inhibiting antibody-induced RBC cross-linking. In addition, it provides new antibody design strategies for utilizing or circumventing cell cross-linking.

# Results

# Generation of rabbit-derived monoclonal antibodies against human CD47

The ECD of human CD47 (HuCD47 ECD) was used to immunize rabbits and produce rabbit CD47 monoclonal antibodies (Fig. 1A). We first measured the antigen binding abilities of the plasma derived from immunized rabbits. Initial evaluation of immunized antisera by enzyme-linked immunosorbent assay (ELISA) revealed a >10,000-fold increase in antigen-binding activity compared to pre-immunized antisera (data not shown). For antibody isolation, we performed single-cell polymerase chain reaction (PCR) experiments to isolate rabbit monoclonal antibodies from immunized rabbits using the biotinylated HuCD47 ECD as the capture reagent. Flow cytometry sorting (FACS) was employed to isolate single CD4 $^{-}$ CD8 $^{-}$ IgM $^{-}$ IgG $^{+}$ HuCD47 ECD $^{+}$ memory B cells. The variable regions of selected antibodies generated directly from single memory B cells were reconstructed with the constant region of human IgG4PE (IgG4-S228P/L235E) to facilitate humanization, followed by assessment of the binding and neutralizing activities with CD47 (data not shown).

![](images/b84475ef81ac853d344b57703beee372284dc042a6481d858482e96ee838b71f.jpg)

![](images/ca091e126179d2762a6e62aa8d62026dd296487fa196625b66649707b3034f12.jpg)

![](images/5cd5ee34ad88761454112fa42e1bf3ef410155a3be44e4b61f2f397fe29129cb.jpg)

![](images/6c44e744a4e4537b77b3a45350d38396cc916a8f66cf4806052bb04275f9bce6.jpg)

![](images/c45e2722d6830a046bb0872661bd3a78b3bfef98be9026d4a7100c0250031381.jpg)

![](images/5f799253842a04e66a71b0f5a76aa30911b157509ccb26e2eb7b15eb5bc57268.jpg)

![](images/8f300f362ac0818cc5d4569a03b258038814ca1a12ff4ec2ff2362b5a3c268f5.jpg)  
Figure 1. Flowchart of rabbit single-cell memory B-cell technology and the characterization of 1C8. A, flowchart of rabbit single-cell memory B-cell technology. B, hemagglutination activity of 1C8. Other CD47 antibodies, Hu5F9 and 9E4 (Reference US 2014/0,140,989 A1) associated with hemagglutination issue, were used as controls. C, binding activity of 1C8 to the HuCD47 ECD. D, binding activity of 1C8 to the CyCD47 ECD. E, binding activity of SIRPα-Fc to the HuCD47 ECD. NC, Unrelated proteins that do not bind to HuCD47 ECD. F, neutralizing activity of 1C8 towards the HuCD47 ECD. G, binding activity of 1C8 to CD47 on human RBCs. Iso-Ctrl, isotype control antibody. The results in (C, D, E, F, G) are presented as the means ± SD. Data are representative of two or three independent experiments.

Anti-CD47 antibodies may cause homotypic clustering of RBCs (hemagglutination), which is one of the reasons for RBC toxicity. To identify antibodies with low RBC toxicity, we performed a human RBC agglutination experiment to select CD47 antibodies that did not induce hemagglutination. Human RBCs were diluted to 2% in phosphate buffer saline (PBS) and incubated with different concentrations of CD47 antibodies at room temperature for 1 to 2 h. Hemagglutination is characterized by the presence of dispersed RBCs, while RBCs that did not undergo hemagglutination precipitate and form red dots at the bottom of the plates. We screened nearly 20 CD47-specific antibodies; only 1C8 showed no hemagglutination (Fig. 1B) and was selected as a candidate for humanization and further in-depth characterization.

ELISA and FACS-based experiments were performed to evaluate 1C8 in vitro. A humanized mouse anti-human CD47 antibody, Hu5F9-G4, which is in the clinical trial stage (20), and an isotype antibody that binds to hepatitis C virus (21) were used as positive and negative controls, respectively. The antigen-binding affinity and neutralizing capacity of 1C8 were quantified by ELISA, demonstrating no significant difference from Hu5F9-G4 in both assays. (Fig. 1, C and F). Prior to neutralizing efficacy evaluation, we pre-tested the activity of SIRPα to ensure the reliability of the experiment (Fig. 1E). In addition, 1C8 cross-reacted with the ECD of cynomolgus CD47 (CyCD47 ECD) (Fig. 1D). Cell-based binding was examined with human RBCs. The results showed that the binding activity of 1C8 to RBCs was significantly lower than that of Hu5F9-G4 (Fig. 1G). In conclusion, the 1C8 antibody showed robust binding activity to human and cynomolgus CD47 but weak binding to RBCs. These properties make it an ideal candidate for a therapeutic CD47 antibody.

# Humanization of 1C8

To humanize 1C8, a 3D structure model was first built using combinations of known structures (PDB codes: 6BA5 (22), 5I8K, 5V6M (23), 6I9I (24)) that share more than $80\%$ sequence identity with 1C8 (Fig. 2A). The online tools Kabat and IMGT were used to identify the complementarity-determining region (CDR) residues. Combined with the structure model information, the heavy chain CDRs (HCDRs) were referenced to IMGT, and the light chain CDRs (LCDRs) were referenced to Kabat (Fig. 2, A and B). The 1C8 variable genes (VH and Vk) were subsequently queried using Ig-BLAST against the human germline VH and Vk databases to identify appropriate human antibody framework regions (FRs) that were suitable for use as templates in CDR grafting. IGHV3/IGHJ6 and IGKV1/IGKJ1 were ultimately identified as templates for 1C8 humanization (Fig. 2C). Next, the key residues in the FRs that may be involved in CDR contacts and interchain contacts and were buried inside based on analysis of the structure model, were marked with an asterisk (*) (Fig. 2C). After CDR grafting, these residues were considered to be back-mutated. Finally, we designed a series of humanized variants (Fig. 2C).

The humanized heavy chains and light chains were recombined with parental light chains (1C8-L0) and heavy

chains (1C8-H0) into new antibodies, and the reactivity of the humanized antibody variants was subsequently examined. The ELISA-binding results indicated that H1L0 and H2L0 lost all or part of their binding activity (Fig. S1, A and B). After removing 1C8-H1 and 1C8-H2, the remaining humanized heavy and light chains could recombine to form new antibodies. The binding and neutralizing activity assay results showed that these antibodies had similar EC $_{50}$ values (the concentration for 50% of the maximal effect); however, the IC $_{50}$ values (the half maximal inhibitory concentration) of H3L2 and H4L2 were slightly higher than that of 1C8 (Fig. S1, C–E). We further assessed the binding kinetics of the antibodies to HuCD47 ECD and CyCD47 ECD using an Octet RED96 instrument. The results revealed that both H3L1 and H4L3 had a 3-fold lower binding affinity to the HuCD47 ECD than the parental antibody 1C8, which did not meet the humanization standard, and the binding affinity ( $K_{d}$ ) values of H3L3 and H4L3 for the HuCD47 ECD and CyCD47 ECD met the humanization standard (Figs. 2D; S1, F–N). H3L3 was closer to 1C8 according to the $K_{on}$ (association rate constant) and $K_{off}$ (dissociation rate constant) parameters and was selected as the final humanized antibody (Hu1C8) (Figs. 2D; S1N). After engineering, the intact chains of Hu1C8 were 96.1% and 98.9% identical to the human heavy chain and light chain, respectively (Fig. 2E).

# Functional characterization of the humanized anti-CD47 antibody Hu1C8 in vitro

The functional activity of Hu1C8 in vitro was characterized in the same manner as 1C8. The antigen binding and neutralization activities of Hu1C8 were examined by ELISA (Fig. 3, A–C). The binding affinities of Hu1C8 and 1C8 were evaluated by FACS using two lymphoma models: CCRF-CEM cells (human T lymphoblasts derived from a 4-year-old female T-ALL patient) and Raji cells (a Burkitt's lymphoma B-cell line). As shown in Figure 3, D and E, Hu1C8 exhibited similar binding activity to 1C8.

To compare the binding of Hu1C8 to normal and tumor cells, we also used a flow cytometry-based binding assay using human aortic endothelial cells (HAECs), human renal cortex proximal tubule epithelial cells (RPTECs), and human RBCs (Fig. 3, F–H). The relative $EC_{50}$ of Hu1C8 for normal cells versus tumor cells was significantly higher than that of Hu5F9-G4 (Figs. 3, D–H; S2A). The results indicate that Hu1C8 has lower binding activities to normal cells, especially RBCs, than to tumor cells. The selective binding is expected to have advantages over antibodies that bind with similar affinity to both normal and tumor cells.

Like 1C8, Hu1C8 did not cause any hemagglutination. In contrast, Hu5F9-G4 caused significant hemagglutination, as previously reported (Figs. 3I; S2, B–D).

We next sought to determine the ability of Hu1C8 to induce macrophage-mediated phagocytosis of tumor cells. Antibody-dependent cellular phagocytosis (ADCP) analysis was performed using CCRF-CEM cells as the targets and macrophages derived from healthy human peripheral blood

![](images/1dac790583946d68bc08b5f20740b2afd27ff5276347d0a895e727cde18346ed.jpg)  
A

B   

<table><tr><td></td><td>Kabat</td><td>IMGT</td></tr><tr><td>HCDR1</td><td>SYAIS</td><td>GFSLSSYA</td></tr><tr><td>HCDR2</td><td>YISSIGDPYYASWVNG</td><td>ISSIGDP</td></tr><tr><td>HCDR3</td><td>SYPGNGDLGRLDI</td><td>ARSYPGNGDLGRLDI</td></tr><tr><td>ED-loop</td><td>TSSTVT</td><td>TSSTVT</td></tr><tr><td>LCDR1</td><td>QSSQSVYRNKYLS</td><td>QSVYRNKY</td></tr><tr><td>LCDR2</td><td>YASTLAS</td><td>YAST</td></tr><tr><td>LCDR3</td><td>AGDYSDDIENA</td><td>AGDYSDDIENA</td></tr></table>

![](images/396714d3a2c1cedbc5525fdbfe6ed9cfc0480e7f3b9d5ecd497e8cb03a956e82.jpg)  
C

D

![](images/13baf334283a677f8edeaaa3ad7f83b47beb8966db993519feafde3eea46c453.jpg)  
Figure 2. Humanization of 1C8. A, the structural model of 1C8. The CDR regions of 1C8 VH and Vκ are coloured blue and red, respectively. B, the sequences of the 1C8 CDR regions were obtained from the Kabat and IMGT databases. C, the amino acid sequence alignments of VH and Vκ of the humanized variant sequences with human germline sequences. D, the relative binding affinity of the humanizing antibodies for the original antibody 1C8. E, the degree of humanization of H3L3.

E   

<table><tr><td></td><td colspan="3">Heavy Chain</td><td colspan="4">Light Chain</td></tr><tr><td>H3L3</td><td>Variable Region</td><td>Constant Region</td><td>Intact Chain</td><td>Variable Region</td><td>Constant Region</td><td>Intact Chain</td><td>Full IgG</td></tr><tr><td rowspan="2">Full-length</td><td>102/118</td><td>330/330</td><td>432/448</td><td>109/111</td><td>107/107</td><td>216/218</td><td>648/666</td></tr><tr><td>86.40%</td><td>100%</td><td>96.40%</td><td>98.20%</td><td>100%</td><td>99.10%</td><td>97.30%</td></tr><tr><td rowspan="2">Fremwork</td><td>72/88</td><td>330/330</td><td>402/418</td><td>78/80</td><td>107/107</td><td>185/187</td><td>587/605</td></tr><tr><td>81.80%</td><td>100%</td><td>96.10%</td><td>97.50%</td><td>100%</td><td>98.90%</td><td>97.00%</td></tr></table>

mononuclear cells (PBMCs) as the effector cells. The results showed that 1C8 and its humanized variant Hu1C8 induced dose-dependent increases in the phagocytosis of tumor cells. At concentrations of 0.1 $\mu$ g/ml, 1 $\mu$ g/ml, and 10 $\mu$ g/ml, Hu1C8 and Hu5F9-G4 induced macrophage-mediated phagocytosis of CCRF-CEM cells to similar extents (Fig. 3, J and K). These data demonstrate that Hu1C8 induces macrophage-mediated phagocytosis of CD47-positive tumor cells. Taken together, these results show that Hu1C8 retains all the biological activities of its parental antibody in vitro.

# Hu1C8 effectively inhibits tumor growth in NSG mice

To evaluate the in vivo antitumor activity of Hu1C8, the Raji lymphoma model was treated with antibodies. Raji cells were implanted subcutaneously into M-NSG mice (NOD.Cg-Prkdc $^{scid}$ Il2rg $^{em1Smoc}$ ; Shanghai model organisms). After the tumor size reached 80 mm $^{3}$ , the mice were randomly divided into seven groups and received antibody treatment. The

antibodies were intraperitoneally injected once every 3 days for six continuous doses. Body weight and the width and length of the tumors were measured every 3 days (Fig. 4A). The data demonstrated that all the Hu1C8 treatment groups exhibited significantly reduced Raji tumor volume and tumor weight compared to the vehicle group (Fig. 4, B–D). Dose-response analyses revealed similar antitumor efficacy between Hu1C8 and Hu5F9-G4 (Figs. 4, B–D; S3, A–G). Moreover, no abnormal body weight changes were observed relative to vehicle controls (Fig. 4E). These results demonstrate that Hu1C8 can inhibit tumor growth.

# Crystal structure of the Hu1C8 Fab-CD47 ECD complex reveals the molecular mechanism of Hu1C8 bearing low hemagglutination and high antitumor activity

To understand the molecular mechanism by which Hu1C8 induces low hemagglutination but exhibits high antitumor activity, we determined the crystal structure of the Hu1C8

![](images/f60d689e0389dee2fced87862b8fc7005db2c2aba7ca2cb94fd9fe85376804fc.jpg)  
A   
B   
C   
D   
E   
F   
G   
H   
J   
|   
K   
Figure 3. Functional characterization of the humanized anti-CD47 antibody Hu1C8. A and B, binding activities of Hu1C8 to the HuCD47 ECD (A) and CyCD47 ECD (B). C, neutralization activity of Hu1C8 towards the HuCD47 ECD. D–H, binding activities of Hu1C8 to CD47 on CCRF-CEM cells (D), Raji cells (E), HAECs (F), RPTECs (G), and human RBCs (H). I, hemagglutination activity of Hu1C8. J, images of macrophage-mediated phagocytosis (20 $^{*}$ ). Green fluorescence indicates macrophages, blue fluorescence indicates tumor cells, and blue fluorescence surrounded by green fluorescence represents macrophages that engulfed tumor cells. Scale bars represent 100 $\mu$ m. K, statistical analysis of the proportion of phagocytosis. The results in (A–H, K) are presented as the means ± SD. Statistical analyses in (K) were performed with two-way ANOVA. "ns" indicates no significant difference. Data are representative of two or three independent experiments.

Fab fragment in complex with the CD47 ECD (amino acids Gln1-Pro121 of HuCD47 with C15A mutation) at a resolution of 2.5 Å. Structural analysis of the Hu1C8 Fab-CD47 ECD complex showed that the Hu1C8 Fab recognized a

unique conformational epitope on the CD47 ECD (Fig. 5A). The L1, L2, L3, H2, and H3 CDR loops of Hu1C8 form a large, shallow pocket to accommodate the CD47 epitope, while the H1 CDR loop does not participate in this

![](images/213795df2cd9ebdb7c4258524b4000980719b925961ab8ea9694b62575750da9.jpg)  
A

![](images/943e9d73537e19e1ec46cc87ac59e18fd2ee95b5008a66842e1f54a647bbaf79.jpg)  
B

![](images/3746827a75db2d0118d8f623c671a168780d4eca22caab14a03516cce8749b30.jpg)  
C

![](images/ee068a06a94ce93fce76fa40a884986eb36287ff511e5c2f3740ea4563def94e.jpg)  
E

![](images/e23e33fbc2d70f76aeff72c134272fe040d163e256cfb8bce74c28de380de6f7.jpg)  
D   
Figure 4. Hu1C8 inhibited tumor growth in vivo. A, schematic diagram showing tumor inoculation and antibody treatment of the mice. B, tumor volume under treatment with varying antibody doses. C, images of tumor tissues. CR, Complete Response. D, tumor weight. E, the curves of body weight. The results are presented as the means ± SD, (n = 6–7 mice per group). Statistical analyses in (B, D, E) were performed with an unpaired t test. *p < 0.05, **p < 0.01, ***p < 0.001, ****p < 0.0001, "ns" indicates no significant difference. Data are representative of two or three independent experiments.

interaction (Fig. 5B). The conformational epitope of CD47 consists mainly of two structural segments from the $\beta$ -sheet of the ECD, namely, residues 37 to 46 ( $\beta$ 3, $\beta$ 4) and 97 to 108 ( $\beta$ 7, $\beta$ 8) (Fig. 5B). The interacting interfaces between Hu1C8 and CD47 are dominated by hydrophilic interactions and bury approximately $756\AA^2$ of the solvent-accessible surface area of Hu1C8 and CD47. In particular, eight residues of CD47 (Tyr37, Lys39, Lys41, Asp46, Glu97, Thr99, Glu104, and Glu106) form a number of salt bridges and hydrogen bonds with several residues of LCDR1 (Tyr30 and Arg31), LCDR2 (Tyr52), LCDR3 (Asp97), and HCDR3 (Tyr96, Asn99, and Asp101) (Fig. 5B). The side chain of Tyr37 is also stabilized by a cation- $\pi$ interaction with Arg31 of LCDR1. In addition to the electrostatic and hydrogen-bonding interactions, a small patch of hydrophobic interactions is also observed, including Asn93 and Thr95 of CD47- $\beta$ 7, Ile105 of CD47- $\beta$ 8, Ile53 of HCDR2, and Asn99 of HCDR3 (Fig. 5B). To support that this conformational epitope does mediate

Hu1C8-CD47 ECD complex binding, we performed alanine-scanning mutagenesis of CD47 ECD. ELISA-based binding analysis showed that alanine substitution of Tyr37, Lys39, Lys41, Asp46, and Glu106 markedly reduced the binding of Hu1C8 to CD47 (Fig. S4). We also found that the N93A, T95A, and I108A mutations of CD47 had insignificant effects on the binding (Fig. S4). These results indicate that the hydrophilic interactions dominate the binding affinity of the Hu1C8-CD47 ECD interaction.

Intriguingly, we found a metal ion bound at the CDR region of Hu1C8, which is coordinated by the side-chain Oδ1 and Oδ2 of Asp93, the main-chain carbonyl of Tyr94, the side-chain Oδ1 of Asp97 on LCDR3, the side-chain Oδ1 of Asp101 on HCDR3, and two water molecules with a pentagonal bipyramid coordination geometry (Fig. 5C). As the side chains of Asp97 on LCDR3 and Asp101 on HCDR3 and the two water molecules not only serve as ligands for the metal ion but also form hydrophilic interactions with the

![](images/2a8ebf289a046f9c2e618413c6806485a17eb3d3d0f35ac489357d46d3ad4eaf.jpg)  
A

![](images/00646380df0eec6482ac285947b3a20eec94a97a037f27ed2121b460cef11c38.jpg)  
B

![](images/7c8112fd3d5b46fd78416ac5850509690c9cce60cc454fc52dd523b85821a007.jpg)  
C

![](images/0908e4a54f05f968c568e5a03d4fcddbc7b6352e82dcb75c4d669ca26d201a32.jpg)  
D   
E

![](images/2bbff14924fe55ce1262cade964cf5cb88b49b4acbd7bc00b0587a018422febd.jpg)

![](images/343267857aacc1dde5ad7ad343388aa604227bd6211ce01ab6d54ae96c31417e.jpg)  
F

![](images/6eb59b5a8b1a5b884ee5fd99aefc50fc0d4fae0311942da4246a5a237479116b.jpg)  
G

![](images/046eed0875d0165b9128db857607f61d6f166b72ed8a98d9ae77206029adcad5.jpg)  
H   
Figure 5. Crystal structure of the Hu1C8 Fab in complex with the CD47 ECD. A, overall structure of the Hu1C8 Fab-CD47 ECD complex shown in ribbon diagram. The heavy and light chains of the Hu1C8 Fab are shown in cyan and green, respectively. The CD47 ECD is shown in pink. B, interactions of the CD47 ECD with the light chain (left) and heavy chain (right) of Hu1C8 Fab. The salt bridges and hydrogen bonds are shown with black dashed lines, and the hydrophobic interactions are shown with yellow dashed lines. C, detailed structure of the CDR region of Hu1C8 involved in the metal ion binding. The $2F_{O}-F_{C}$ electron density (contoured at 1.0 σ level) for the metal ion and the interacting residues is shown with a slate-blue mesh. D, binding activity of Hu1C8 to HuCD47 ECD in the presence of 2 mM EDTA. The results are presented as the means ± SD. E, the addition of metal ions restored the binding activity of Hu1C8 to HuCD47 ECD in the presence of 2 mM EDTA. The results are presented as the means ± SD of two independent experiments. F, structural comparison of the Hu1C8 Fab-CD47 ECD complex with the SIRPα-CD47 ECD complex (PDB code: 2JJS) (26) and the Hu5F9 diabody-CD47 ECD complex (PDB code: 5IWL) (25). The superposition of the three complexes was based on the CD47 ECD. The Hu5F9 diabody is a fusion protein of the heavy and light

epitope residues Lys39, Lys41, and Asp46 of CD47, we speculated that the binding of the metal ion to the CDR region of Hu1C8 played an important role in the specific recognition and binding of Hu1C8 with CD47 and the formation of the Hu1C8–CD47 complex. Indeed, an in vitro binding assay showed that removal of the metal ion by EDTA chelation abolished the interaction between CD47 and Hu1C8 (Fig. 5D). Replenishment of EDTA-treated Hu1C8 with several bivalent cations commonly found in organisms showed that compared to $Fe^{2+}$ , $Mg^{2+}$ and $Zn^{2+}$ , $Ca^{2+}$ could efficiently restore the binding of Hu1C8 to CD47 (Fig. 5E). To analyze the types and abundances of metal ions in the protein solution, we performed ICP-OES (inductively coupled plasma optical emission spectrometer) analysis and the results showed that $Ca^{2+}$ is the most abundant ( $>95\%$ ) metal ion in the protein solution. As the concentration of $Ca^{2+}$ is much higher than that of $Fe^{2+}$ , $Mg^{2+}$ , and $Zn^{2+}$ in the cell culture medium and inside the cells, we assigned the bound metal ion in the structure as $Ca^{2+}$ and believe that the bound $Ca^{2+}$ is biologically relevant and plays an important role in helping Hu1C8 to create a unique antigen binding site that specifically recognizes and binds the conformational epitope of CD47.

To understand the underlying mechanism by which Hu1C8 maintains a similar activity of inhibiting cancer cell growth to Hu5F9-G4 but has a low activity to induce hemagglutination, we compared the structure of the Hu1C8-CD47 complex with that of the Hu5F9-CD47 complex (PDB code: 5IWL) (25) and the SIRPα-CD47 complex (PDB code: 2JJS) (26) (Fig. 5F). The structural comparison showed that although both Hu1C8 and Hu5F9 bind to the β-sheet of CD47-ECD to occupy part of the SIRPα-binding site and thus block the binding of SIRPα, they recognize and bind to different regions of the β-sheet of CD47-ECD with distinct binding orientations (Fig. 5, F and G). Specifically, SIRPα mainly binds to the upper part of the β-sheet of CD47-ECD, Hu5F9 mainly binds to the loops on the upper part of the β-sheet of CD47-ECD, and Hu1C8 mainly binds to the lower part of the β-sheet of CD47-ECD (Fig. 5, F and G). Further structural analysis of the CD47 ECD in complexes with other antibodies in the PDB databank showed that the recognition and targeting of these loops together with the upper part of the β-sheet of the CD47 ECD, seem to be a common feature of many CD47 antibodies (Fig. S5). These results indicate that Hu1C8 recognizes a unique conformational epitope on the CD47 ECD and binds to the CD47 ECD with a distinct binding orientation different from the other antibodies (Figs. 5, F and G; S5).

Further superposition of the Hu1C8-CD47 and Hu5F9-CD47 complexes onto the full-length IgG4 antibody and the full-length CD47 revealed that the different binding orientations of Hu1C8 and Hu5F9 to the CD47 ECD might yield different binding modes with CD47, leading to differences in RBC hemagglutination (Fig. 5H). Both Hu5F9 and Hu1C8

could bind two CD47 molecules in a Y-shaped conformation. However, as CD47 binds to one Fab of Hu5F9 in a pose almost parallel to the Fab arm, the two CD47 molecules recognized by a single full-length Hu5F9 antibody are oriented approximately perpendicular to each other's Fab arm (Fig. 5H left). This binding mode provides sufficient space for the Hu5F9 antibody to bind to two CD47 molecules on different cells, leading to RBC hemagglutination. On the other hand, since CD47 binds to the Fab of Hu1C8 at an approximately $130^{\circ}$ angle to the Fab arm, the two CD47 molecules recognized by one Hu1C8 antibody are in a nearly parallel orientation, and their spacing is narrow (Fig. 5H right). This binding mode is unable to allow one Hu1C8 antibody to crosslink two cells simultaneously due to its conformational changes, thus preventing RBC hemagglutination. This might explain why Hu1C8 does not tend to bind to two cells simultaneously and has low RBC toxicity.

# Discussion

Numerous studies have shown that CD47 is essential for the treatment of a variety of malignancies. Blockade of the CD47/SIRPα axis enhances macrophage-dependent phagocytosis of tumor cells, establishing this immune checkpoint as a therapeutic target in cancer immunotherapy (18). The clinical development of CD47-based therapies has achieved breakthrough progress in recent trials (27). However, this therapeutic mechanism also targets CD47 molecules on the surface of RBCs, inducing phagocytosis-mediated destruction and resulting in anemia during clinical use. Therefore, reducing RBC toxicity is a critical issue in the development of CD47 antagonists. To increase the efficacy and safety of CD47 antagonists, many next-generation anti-CD47 antibodies with reduced RBC toxicity have been developed (28–31). Meanwhile, bispecific antibodies, SIRPα-Fc fusion proteins, and small-molecule inhibitors have been developed to reduce hematotoxicity. In this study, we focused on developing a novel anti-CD47 antibody with unique epitope recognition and antigen binding mode to minimize RBC toxicity.

Hemagglutination is a reaction that causes the clumping of RBCs. Specific antigens or receptors exist on the surface of RBCs. When they specifically bind to corresponding substances such as antibodies, viruses, and lectins, the cross-linking action will cause the RBCs to interconnect with each other and form agglutinated clumps. Anti-CD47 antibodies may target the CD47 on the surface of RBCs and cause cellular clumping and lattice structure formation, which can cause coagulation. Interestingly, in our structural study, when one arm of a Hu1C8 molecule bound to the unique epitope of CD47 on RBCs with distinct binding orientations, the other arm was restricted to the same cell membrane. Therefore, the complex could not act as a bridge between two cells, thereby losing the ability to induce the formation of lattice structures.

variable domains of Hu5F9. For clarity, only one domain from each diabody is shown. G, the CD47-binding interface showing residues interacting with only SIRPα (purple), only Hu5F9 (yellow), only Hu1C8 (cyan), or both ligands (red). H, the structures of the Hu1C8 Fab-CD47 ECD complex and the Hu5F9 diabody-CD47 ECD complex were superimposed on the structures of whole IgG4 antibody (PDB code: 5DK3) (45) and full-length CD47 (PDB code: 7MYZ) (46), showing that Hu1C8 and Hu5F9 bind to CD47 in different binding orientations, thus yielding different RBC toxicities.

The structural and mechanistic study of Hu1C8 validated the hypothesis that the Fab binding orientation of anti-CD47 antibodies correlates with hemagglutination potential (28) and provided structural insights for developing non-hemagglutinating CD47 antibodies.

In addition, these results reaffirm that epitope localization critically governs antibody activity and provides a structural basis for the rational design of therapeutic mAbs with tailored functional properties. For anti-CD47 antibodies, selecting the antigen-binding epitope is particularly important to avoid hemagglutination caused by cell crosslinking. In fact, Yu et al. have shown that the stimulatory activity of human anti-CD40 antibodies was shown to decrease as epitopes became closer to the cell membrane (32). They speculate that the importance of the epitope location is related to the accessibility of the Fc domain. Specifically, the Fc domain of antibodies that are closer to the membrane will not be able to optimally bind to FcγR. Anti-CD40 antibodies frequently rely on secondary crosslinking via Fcγ receptors (FcγR) for biological activity (33); however, excessive activation may lead to toxic side effects. In conclusion, the epitope and recognition angle of an antibody are likely to constrain the accessibility of the other arm or the Fc region, which provides valuable guidance for antibody design. By strategically leveraging or circumventing cell-crosslinking through such mechanisms, antibodies can achieve an optimal balance between therapeutic efficacy and safety.

In addition to their direct applicability in immunotherapeutics, the antibody properties elucidated in this study represent a rather rare phenomenon. The diversity of antigen-binding specificities of antibodies is generated by the genetic processes of recombination and mutation. Accumulating evidence suggests that the immune system can exploit additional strategies to diversify the repertoire of antigen specificities. These unconventional mechanisms exclusively target the antigen-binding sites of immunoglobulins and include the insertion of large amino acid sequences, post-translational modifications, conformational heterogeneity, and use of nonprotein cofactor molecules (34). Among these, the unique ligation properties of metal ions are widely utilized by proteins, particularly the metalloproteins but are rarely exploited by antibodies. Zhou et al. first reported that a CD4-reactive Ab Q425 requires calcium for antigen recognition (35). In this study, we observed a similar phenomenon with a rabbit antibody against CD47. Specifically, X-ray crystallographic analyses show that Hu1C8 requires a bivalent metal ion to form robust interaction with CD47, suggesting that the immune system can exploit additional strategies to diversify the repertoire of antigen specificities.

# Experimental procedures

# Cells, antibodies, and recombinant proteins

ExpiCHO-S cells (Gibco) were cultured in ExpiCHO expression medium (Gibco) supplemented with 1% penicillin–streptomycin (Gibco) at 37 °C in 8% CO $_{2}$ . Raji cells and CCRF-CEM cells were cultured in RPMI 1640 (Gibco)

supplemented with 10% fetal bovine serum (FBS) and 2% penicillin-streptomycin at 37 °C in 5% CO $_{2}$ . HAECs and RPTECs were generated and cultured in Dulbecco's modified Eagle's medium (DMEM; Gibco) supplemented with 10% FBS and 2% penicillin-streptomycin at 37 °C in 5% CO $_{2}$ . These cells are from the National Collection of Authenticated Cell Cultures. Human RBCs and PBMCs were purchased from Milestone Biotechnologies.

The Hu5F9-G4 VH and V $\kappa$ sequences were commercially synthesized (Shanghai Generay Biotech Co., Ltd) in accordance with the patents (WO 2011/143,624 A2) and were cloned and inserted into the human IgG4PE scaffold. The negative control antibody (8D6) was generated in our laboratory (21). These antibodies were expressed in ExpiCHO-S cells.

# Animal immunization

The HuCD47 ECD, which had a 6 × His tag fused to the C-terminus (amino acids Gln1-Pro121; Acro Biosystems), was used as the antigen. Male New Zealand White rabbits weighing 2 to 2.5 kg were subcutaneously immunized at multiple points with 1 mg of antigen in the presence of complete Freund's adjuvant, followed by two boosters with the same dose of antigen in the presence of incomplete Freund's adjuvant. Immunization was performed every 3 weeks, and serum samples were collected 7 days after the third immunization. The rabbits were housed at the Shanghai Tengda Rabbit Industry Professional Cooperative. All animal experiments were performed in accordance with the relevant regulations of the Shanghai Tengda Rabbit Industry Professional Cooperative.

# Isolation of rabbit monoclonal antibodies

PBMCs were isolated from the blood of immunized rabbits using Lympholyte-Mammal density separation medium (Cedarlane) according to the manufacturer's instructions. The HuCD47 ECD was labelled with EZ-Link Sulfo-NHS-LC-Biotin (Thermo Fisher Scientific) as a sorting probe. PBMCs were stained with Fixable Viability Stain 510 (BD Biosciences), Alexa Fluor 647 donkey anti-rabbit IgG (BioLegend), goat anti-rabbit IgM-FITC (Southern Biotech), mouse anti-rabbit CD4-FITC (Bio-Rad), mouse anti-rabbit CD8-FITC (Bio-Rad), mouse anti-rabbit T lymphocyte-FITC (Bio-Rad), and biotinylated HuCD47 ECD-streptavidin-SA BV421. Single HuCD47 ECD-specific memory B cells (FITC $^{-}$ /APC $^{+}$ /BV421 $^{+}$ ) were isolated using a Sony MA900 instrument and sorted into a 96-well PCR plate containing lysis buffer. The antibody VH and V $\kappa$ in each cell were amplified by RT-PCR and nested PCR using primer panels as previously described (36). The VH and V $\kappa$ genes were sequenced, cloned and inserted into human IgG4PE and IgK expression vectors.

# Expression and purification of antibodies

The VH and Vk gene expression plasmids were co-transfected into ExpiCHO-S cells using an ExpiFectamine CHO Transfection Kit (Invitrogen) according to the

# Structural mechanism of an Anti-CD47 antibody

manufacturer's instructions. The supernatants were harvested, and the rabbit monoclonal antibodies were purified using Protein A Sepharose (GE Healthcare) according to the manufacturer's instructions and dialyzed against PBS.

# ELISA

To determine the binding properties of the sera and antibodies, 96-well microwell plates (Nunc) were coated with 1 $\mu$ g/ml HuCD47 ECD or CyCD47 ECD (Acro Biosystems) protein in 0.1 M PBS and incubated overnight at 4 °C, followed by blocking with 2% bovine serum albumin (BSA) in PBST (0.05% Tween-20 in PBS) for 2 h. The plates were washed and incubated with serially diluted sera or antibodies at 37 °C for 2 h. The samples were washed three times, and depending on the sample, horseradish peroxidase (HRP)-conjugated goat anti-rabbit IgG antibody (1:4000; R&D Systems), or anti-human Fc HRP antibody (Sigma-Aldrich, cat. no. A0170) was used to detect the bound antibodies. The EC $_{50}$ was calculated using Prism 8.

To test the ability of the antibodies to block the binding of CD47 to its receptor SIRPα, SIRPα-Fc (Acro Biosystems) was precoated on 96-well plates, and serially diluted antibodies were incubated with the HuCD47 ECD for 1 h at 37 °C. The mixture was subsequently added to the plates and incubated at 37 °C. After 1 h, the plates were washed, and the HuCD47 ECD that bound to SIRPα was examined with an HRP-conjugated mouse anti-His monoclonal antibody. The 50% inhibitory concentration (IC $_{50}$ ) was calculated using Prism 8.

# FACS-based binding and blocking assays

To assess whether the antibodies could bind to CD47 on the surface of cells, serially diluted antibodies were incubated with tumor cells, normal cells, or RBCs that had been stained with Fixable Viability Stain 780 (BD Biosciences) at 4 °C in the dark for 30 min. The cells were subsequently washed three times, and the antibodies bound to the cells were examined with FITC-conjugated anti-human IgG (BioLegend), followed by FACS analysis with a BD Fortessa. For blocking assays, serially diluted antibodies were incubated with Fixable Viability Stain 780-stained tumor cells in the presence of 5 μg/ml bio-SIRPα-Fc (SIRPα-Fc labelled with EZ-Link Sulfo-NHS-LC-Biotin) at 4 °C for 30 min. After the samples were washed, the bound bio-SIRPα-Fc was examined using streptavidin-conjugated BV421 (BD Biosciences), followed by FACS analysis with a BD Fortessa. The data were analyzed by FlowJo V10 and Prism 8.

# Biolayer interferometry (BLI) analysis

Biolayer interferometry was performed using an Octet Red96 instrument (ForteBio, Inc.) to analyze the $K_{d}$ between the antibodies and CD47. 5 $\mu$ g/ml antibody solution was immobilized on an anti-human IgG-Fc-coated biosensor surface for 360 s. The baseline interference phase was measured for 180 s in kinetics buffer (KB: 1 × PBS, 0.1% BSA, and 0.02% Tween-20). The sensors were then immersed in 2-fold serial dilutions of HuCD47 ECD or CyCD47 ECD in KB

to examine the association phase for 360 s, followed by immersion of the sensors in KB for 600 s for the dissociation phase. The mean $K_{on}$ , $K_{off}$ , and apparent $K_{d}$ values were determined from all binding curves that were globally fit to a 1:1 Langmuir binding model with an $R^{2}$ value $\geq 0.95$ by ForteBio Data Analysis 7.0 software.

# Hemagglutination analysis

To evaluate the hemagglutination capacity of the antibodies, human RBCs were washed and diluted 2% in PBS in a V-bottom-shaped 96-well plate. Then, the antibodies were serially diluted 5-fold from 100 $\mu$ g/ml and added to the RBCs at a 1:1 volume ratio. The plates were incubated at room temperature for 1 to 2 h. Evidence of hemagglutination is the presence of unsettled RBCs, which appears as a diffuse haze compared to the punctate red dot of nonhemagglutinized RBCs.

# In vitro phagocytosis assay

Human PBMC suspensions ( $6 \times 10^{5}$ cells/ml) in RPMI 1640 containing 50 ng/ml M-CSF (Sino Biological) were plated in 96-well plates (PerkinElmer) at 100 $\mu$ l/well and differentiated into macrophages for 6 to 7 days until the monocyte-derived macrophages (MDMs) became adherent and the other cells were washed away by culture media. CCRF-CEM cells were labelled with CellTrace Blue (Invitrogen) at 37 °C in the dark for 20 min. The CCRF-CEM cells were then washed and resuspended at $6 \times 10^{5}$ cells/ml in RPMI 1640 medium, followed by being added to MDMs at 50 $\mu$ l/well. Meanwhile, different concentrations of antibodies were added. Phagocytosis was allowed for 3 h at 37 °C in the dark. Since CCRF-CEM cells are suspension cells, the non-phagocytosed CCRF-CEM cells were removed by washing with culture media three times. The MDMs were stained with FITC-conjugated anti-human CD14 (BioLegend) in situ. Phagocytosis was analyzed using an Opera (PerkinElmer). Macrophages were identified by green fluorescence (488 nm) and enumerated. Phagocytosed tumor cells were quantified via blue fluorescence (365 nm). The number of phagocytosis-positive macrophages was recorded using green fluorescence that encapsulates the blue fluorescence. The phagocytic ratio was calculated as the proportion of tumor cell-engulfing macrophages relative to the total macrophage population.

# Antitumor activity of the antibodies in vivo

M-NSG mice xenografted with Raji tumor cells were used to evaluate the antitumor activity of Hu1C8. When the tumor volume reached approximately $80 \, mm^{3}$ , the mice were randomized into seven groups and then treated with the antibodies. The antibodies were injected intraperitoneally once every 3 days for six continuous doses. Body weight and the width and length of the tumors were measured every 3 days, and the following formula was used: tumor volume = length x width x width/2. On Day 18, the mice were sacrificed, and the tumor tissues were collected for both photographic documentation and weighing. The mice were housed under

pathogen-free conditions. This protocol for animal experiments was approved by the Institutional Animal Care and Use Committee of the Center for Excellence in Molecular and Cellular Sciences.

# Antibody humanization

The rabbit antibodies were humanized by a CDR-grafting strategy. CDRs in the heavy and light chains of antibodies were identified by a combination of a 3D structure model and the Abysis online tools (http://www.abysis.org/abysis/). The online platform allows users to input antibody sequences and extract CDR information according to the database you have selected, such as Kabat and IMGT. The sequences of the rabbit antibodies were aligned with the human germline VH and V $\kappa$ databases to identify the most closely related human germline sequences for CDR grafting. After the CDRs were grafted, human back to rabbit mutations were introduced in the key residues involved in the function of the antibody in the FRs. The sequences of humanization antibodies were commercially synthesized and cloned into human IgG4PE and Ig $\kappa$ expression vectors. The expression and purification of the humanized antibodies were performed as previously described.

# Crystallization, data collection, and structure determination

The Fab fragment of Hu1C8 was generated by papain digestion of the Hu1C8 antibody and purified by Protein A agarose (GE Healthcare) and gel filtration on a Superdex 200 10/300 column (Cytiva) in buffer containing 20 mM Tris pH 7.5 and 150 mM NaCl. The CD47 ECD (residues 1–121), with a C15A mutation (26) and C-terminal 6 histidine tag, was cloned into pcDNA3.4. CD47 ECD was expressed transiently in ExpiCHO-S cells in the presence of 8.6 $\mu$ M Kifunensine. CD47 ECD were purified by HisTrap excel resin (Cytiva) according to the manufacturer's instructions. To further reduce the oligosaccharide chains attached on protein surface, CD47 ECD was incubated with endoglycosidase-H (endoH) at 37 °C for 1 h followed by size exclusion chromatography purification with a Superdex 75 column (GE Healthcare) and the fraction containing polished CD47 ECD was collected. The purified Fab Hu1C8 was mixed with CD47 ECD at 1:1 stoichiometric ratio and the protein complex was then concentrated to 15 mg/ml prior to crystallization experiments.

Crystallization was carried out at $16\ ^{\circ}C$ using the hanging-drop vapor diffusion method by mixing equal volumes (1 $\mu$ l) of the Hu1C8 Fab-CD47 ECD complex solution and the reservoir solution. Crystals of the Hu1C8 Fab-CD47 ECD complex were grown in drops containing a reservoir solution of 0.1 M HEPES (pH 7.0) and 20% (w/v) polyethylene glycol 3350. The crystals were transferred into the cryoprotectant consisting of the reservoir solution and 20% (v/v) glycerol for cryoprotection, followed by flash-cooling into liquid nitrogen. X-ray diffraction data were collected at BL18U1 of National Facility for Protein Science Shanghai. Diffraction data indexing, integration, and scaling were performed using

HKL2000 (37). The structure of the Hu1C8 Fab-CD47 ECD complex was solved by molecular replacement method as implemented in Phenix (38) using the crystal structures of anti-HSA Fab (PDB code 5FUZ) (39) and CD47 ECD (PDB code 2JJS) (26) as the search models. Model building was performed using Coot (40), and structure refinement was performed using Phenix (38). The stereochemistry and quality of the structure model were analyzed using programs in the CCP4 suite (41). The statistics of the diffraction data, the structure refinement and the final structure model are summarized in Table S1.

# Data availability

The crystal structure of human CD47 ECD bound to Fab of Hu1C8 has been deposited in the Protein Data Bank with accession code 8ZCA (https://www.rcsb.org/structure/8ZCA). All other data are available in the main text or in the supporting information section.

Supporting information—This article contains supporting information (25, 26,42–44).

Acknowledgments—We thank the Core Facilities of Chemical Biology, Cell Biology, and Molecular Biology of the Center for Excellence in Molecular Cell Science, Chinese Academy of Sciences, for their technical support, and the staff at beamline BL02U1 of Shanghai Synchrotron Radiation Facility (SSRF) and beamline BL18U of National Center for Protein Science in Shanghai (NCPSS) for technical assistance in diffraction data collection.

Author contributions—B. S., J. D., X. S., Z. L., C. Y., Z. C., and X. L. writing–review & editing; B. S., J. D., and Q. D. supervision; B. S., Q. D., L. M., and C. Y. project administration; B. S., R. W., S. C., S. W., J. D., K. C., X. S., J. Y., Z. L., C. Y., J. Y., Z. C., X. L., and D. Z. methodology; B. S. conceptualization, J. D. Resources. J. D., Z. C., and X. L. visualization; J. D., X. S., Q. D., Z. L., C. Y., Z. C., and X. L. validation; J. D. and Z. C. software; J. D., Z. L., C. Y., Z. C., J. X., and X. L. investigation; J. D., Z. L., Z. C., and X. L. data curation; X. S., Z. L., and X. L. formal analysis; Z. C. and X. L. writing–original draft.

Funding and additional information—This work was supported by the National Natural Science Foundation of China (32071190 and 32270991) and Shanghai Science and Technology Innovation Action (21JC1405800, 21ZR1470600) and Shanghai Municipal Science and Technology Major Project (ZD2021CY001).

Conflict of interest—The authors declare that they have no conflicts of interest with the contents of this article.

Abbreviations—The abbreviations used are: ADCP, Antibody-dependent cellular phagocytosis; CD47, Cluster of differentiation 47; CDR, complementarity-determining region; DC, dendritic cells; ECD, extracellular domain; FACS, Flow cytometry sorting; HCCDRs, heavy chain CDRs; IAP, integrin-associated protein; LCCDRs, light chain CDRs; PBMCs, peripheral blood mononuclear cells; PCR, polymerase chain reaction; RBCs, red blood cells.

# References

1. Lindberg, F. P., Gresham, H. D., Schwarz, E., and Brown, E. J. (1993) Molecular cloning of integrin-associated protein: an immunoglobulin family member with multiple membrane-spanning domains implicated in alpha v beta 3-dependent ligand binding. J. Cell Biol. 123, 485–496   
2. Matozaki, T., Murata, Y., Okazawa, H., and Ohnishi, H. (2009) Functions and molecular mechanisms of the CD47-SIRPalpha signalling pathway. Trends Cell Biol. 19, 72–80   
3. Barclay, A. N., and Van den Berg, T. K. (2014) The interaction between signal regulatory protein alpha (SIRPalpha) and CD47: structure, function, and therapeutic target. Annu. Rev. Immunol. 32, 25–50   
4. Soto-Pantoja, D. R., Kaur, S., and Roberts, D. D. (2015) CD47 signaling pathways controlling cellular differentiation and responses to stress. Crit. Rev. Biochem. Mol. Biol. 50, 212–230   
5. Bian, H. T., Shen, Y. W., Zhou, Y. D., Nagle, D. G., Guan, Y. Y., Zhang, W. D., et al. (2022) CD47: beyond an immune checkpoint in cancer treatment. Biochim. Biophys. Acta Rev. Cancer 1877, 188771   
6. van Beek, E. M., Cochrane, F., Barclay, A. N., and van den Berg, T. K. (2005) Signal regulatory proteins in the immune system. J. Immunol. 175, 7781–7787   
7. Jaiswal, S., Jamieson, C. H. M., Pang, W. W., Park, C. Y., Chao, M. P., Majeti, R., et al. (2009) CD47 is upregulated on circulating hematopoietic stem cells and leukemia cells to avoid phagocytosis. Cell 138, 271–285   
8. Chao, M. P., Alizadeh, A. A., Tang, C., Myklebust, J. H., Varghese, B., Gill, S., et al. (2010) Anti-CD47 antibody synergizes with rituximab to promote phagocytosis and eradicate non-Hodgkin lymphoma. Cell 142, 699–713   
9. Rendtlew Danielsen, J. M., Knudsen, L. M., Dahl, I. M., Lodahl, M., and Rasmussen, T. (2007) Dysregulation of CD47 and the ligands thrombospondin 1 and 2 in multiple myeloma. Br. J. Haematol. 138, 756–760   
10. Arrieta, O., Aviles-Salas, A., Orozco-Morales, M., Hernández-Pedro, N., Cardona, A. F., Cabrera-Miranda, L., et al. (2020) Association between CD47 expression, clinical characteristics and prognosis in patients with advanced non-small cell lung cancer. Cancer Med. 9, 2390–2402   
11. Shi, M., Gu, Y., Jin, K., Fang, H., Chen, Y., Cao, Y., et al. (2021) CD47 expression in gastric cancer clinical correlates and association with macrophage infiltration. Cancer Immunol. Immunother. 70, 1831–1840   
12. Kim, H., Lee, J. W., Lee, E., Kang, Y., and Ahn, J. M. (2021) Correlation of CD47 expression with adverse clinicopathologic features and an unfavorable prognosis in colorectal adenocarcinoma. Diagnostics (Basel) 11, 668   
13. Oldenborg, P. A., Zheleznyak, A., Fang, Y. F., Lagenaur, C. F., Gresham, H. D., and Lindberg, F. P. (2000) Role of CD47 as a marker of self on red blood cells. Science 288, 2051–2054   
14. Oldenborg, P. A., Gresham, H. D., Chen, Y., Izui, S., and Lindberg, F. P. (2002) Lethal autoimmune hemolytic anemia in CD47-deficient non-obese diabetic (NOD) mice. Blood 99, 3500–3504   
15. Chao, M. P., Weissman, I. L., and Majeti, R. (2012) The CD47-SIRPalpha pathway in cancer immune evasion and potential therapeutic implications. Curr. Opin. Immunol. 24, 225–232   
16. Majeti, R., Chao, M. P., Alizadeh, A. A., Pang, W. W., Jaiswal, S., Gibbs, K. D., et al. (2009) CD47 is an adverse prognostic factor and therapeutic antibody target on human acute myeloid leukemia stem cells. Cell 138, 286–299   
17. Chao, M. P., Alizadeh, A. A., Tang, C., Jan, M., Weissman-Tsukamoto, R., Zhao, F., et al. (2011) Therapeutic antibody targeting of CD47 eliminates human acute lymphoblastic leukemia. Cancer Res. 71, 1374–1384   
18. Veillette, A., and Chen, J. (2018) SIRPalpha-CD47 immune checkpoint blockade in anticancer therapy. Trends Immunol. 39, 173–184   
19. Sikic, B. I., Lakhani, N., Patnaik, A., Shah, S. A., Chandana, S. R., Rasco, D., et al. (2019) First-in-Human, first-in-class phase I trial of the anti-CD47 antibody Hu5F9-G4 in patients with advanced cancers. J. Clin. Oncol. 37, 946–953

20. Liu, J., Wang, L., Zhao, F., Tseng, S., Narayanan, C., Shura, L., et al. (2015) Pre-clinical development of a humanized anti-CD47 antibody with anti-cancer therapeutic potential. PLoS One 10, e0137345   
21. Yi, C., Xia, J., He, L., Ling, Z., Wang, X., Yan, Y., et al. (2021) Junctional and somatic hypermutation-induced CX(4)C motif is critical for the recognition of a highly conserved epitope on HCV E2 by a human broadly neutralizing antibody. Cell Mol Immunol 18, 675–685   
22. Qi, J., Li, X., Peng, H., Cook, E. M., Dadashian, E. L., Wiestner, A., et al. (2018) Potent and selective antitumor activity of a T cell-engaging bispecific antibody targeting a membrane-proximal epitope of ROR1. Proc. Natl. Acad. Sci. U. S. A. 115, E5467–E5476   
23. Pan, R., Qin, Y., Banasik, M., Lees, W., Shepherd, A. J., Cho, M. W., et al. (2018) Increased epitope complexity correlated with antibody affinity maturation and a novel binding mode revealed by structures of rabbit antibodies against the third variable loop (V3) of HIV-1 gp120. J. Virol. 92   
24. Allen, E. R., Krumm, S. A., Raghwani, J., Halldorsson, S., Elliott, A., Graham, V. A., et al. (2018) A protective monoclonal antibody targets a site of vulnerability on the surface of rift valley fever virus. Cell Rep. 25, 3750–3758.e3754   
25. Weiskopf, K., Jahchan, N. S., Schnorr, P. J., Cristea, S., Ring, A. M., Maute, R. L., et al. (2016) CD47-blocking immunotherapies stimulate macrophage-mediated destruction of small-cell lung cancer. J. Clin. Invest. 126, 2610–2620   
26. Hatherley, D., Graham, S. C., Turner, J., Harlos, K., Stuart, D. I., and Barclay, A. N. (2008) Paired receptor specificity explained by structures of signal regulatory proteins alone and complexed with CD47. Mol. Cell 31, 266–277   
27. Ye, Z. H., Yu, W. B., Huang, M. Y., Chen, J., and Lu, J. J. (2023) Building on the backbone of CD47-based therapy in cancer: combination strategies, mechanisms, and future perspectives. Acta Pharm. Sin B 13, 1467–1487   
28. Qu, T., Zhong, T., Pang, X., Huang, Z., Jin, C., Wang, Z. M., et al. (2022) Ligufalimab, a novel anti-CD47 antibody with no hemagglutination demonstrates both monotherapy and combo antitumor activity. J. Immunother. Cancer 10, e005517   
29. Thaker, Y. R., Rivera, I., Pedros, C., Singh, A. R., Rivero-Nava, L., Zhou, H., et al. (2022) A novel affinity engineered anti-CD47 antibody with improved therapeutic index that preserves erythrocytes and normal immune cells. Front. Oncol. 12, 884196   
30. Xu, Z., Gao, J., Yao, J., Yang, T., Wang, D., Dai, C., et al. (2021) Preclinical efficacy and toxicity studies of a highly specific chimeric anti-CD47 antibody. FEBS Open Bio. 11, 813–825   
31. Peluso, M. O., Adam, A., Armet, C. M., Zhang, L., O'Connor, R. W., Lee, B. H., et al. (2020) The Fully human anti-CD47 antibody SRF231 exerts dual-mechanism antitumor activity via engagement of the activating receptor CD32a. J. Immunother. Cancer 8, e000413   
32. Yu, X., Chan, H. T. C., Orr, C. M., Dadas, O., Booth, S. G., Dahal, L. N., et al. (2018) Complex interplay between epitope specificity and isotype dictates the biological activity of anti-human CD40 antibodies. Cancer Cell 33, 664–675.e664   
33. Dahan, R., Barnhart, B. C., Li, F., Yamniuk, A. P., Korman, A. J., and Ravetch, J. V. (2016) Therapeutic activity of agonistic, human anti-CD40 monoclonal antibodies requires selective FcgammaR engagement. Cancer Cell 29, 820–831   
34. Kanyavuz, A., Marey-Jarossay, A., Lacroix-Desmazes, S., and Dimitrov, J. D. (2019) Breaking the law: unconventional strategies for antibody diversification. Nat. Rev. Immunol. 19, 355–368   
35. Zhou, T., Hamer, D. H., Hendrickson, W. A., Sattentau, Q. J., and Kwong, P. D. (2005) Interfacial metal and antibody recognition. Proc. Natl. Acad. Sci. U. S. A. 102, 14575–14580   
36. Ojima-Kato, T., Hashimura, D., Kojima, T., Minabe, S., and Nakano, H. (2015) In vitro generation of rabbit anti-Listeria monocytogenes monoclonal antibody using single cell based RT-PCR linked cell-free expression systems. J. Immunol. Methods 427, 58–65   
37. Otwinowski, Z., and Minor, W. (1997) Processing of X-ray diffraction data collected in oscillation mode. Methods Enzymol. 276, 307–326

38. Adams, P. D., Afonine, P. V., Bunkóczi, G., Chen, V. B., Davis, I. W., Echols, N., et al. (2010) PHENIX: a comprehensive Python-based system for macromolecular structure solution. Acta Crystallogr. D Biol. Crystallogr. 66, 213–221   
39. Adams, R., Griffin, L., Compson, J. E., Jairaj, M., Baker, T., Ceska, T., et al. (2016) Extending the half-life of a fab fragment through generation of a humanized anti-human serum albumin Fv domain: an investigation into the correlation between affinity and serum half-life. MAbs 8, 1336–1346   
40. Emsley, P., and Cowtan, K. (2004) Coot: model-building tools for molecular graphics. Acta Crystallogr. D Biol. Crystallogr. 60, 2126–2132   
41. Winn, M. D., Ballard, C. C., Cowtan, K. D., Dodson, E. J., Emsley, P., Evans, P. R., et al. (2011) Overview of the CCP4 suite and current developments. Acta Crystallogr. D Biol. Crystallogr. 67, 235–242

42. Li, Y., Liu, J., Chen, W., Wang, W., Yang, F., Liu, X., et al. (2023) A pH-dependent anti-CD47 antibody that selectively targets solid tumors and improves therapeutic efficacy and safety. J. Hematol. Oncol. 16, 2   
43. Pietsch, E. C., Dong, J., Cardoso, R., Zhang, X., Chin, D., Hawkins, R., et al. (2017) Anti-leukemic activity and tolerability of anti-human CD47 monoclonal antibodies. Blood Cancer J. 7, e536   
44. Wang, R., Zhang, C., Cao, Y., Wang, J., Jiao, S., Zhang, J., et al. (2023) Blockade of dual immune checkpoint inhibitory signals with a CD47/PD-L1 bispecific antibody for cancer treatment. Theranostics 13, 148–160   
45. Scapin, G., Yang, X., Prosise, W. W., McCoy, M., Reichert, P., Johnston, J. M., et al. (2015) Structure of full-length human anti-PD1 therapeutic IgG4 antibody pembrolizumab. Nat. Struct. Mol. Biol. 22, 953–958   
46. Fenalti, G., Villanueva, N., Griffith, M., Pagarigan, B., Lakkaraju, S. K., Huang, R. Y. C., et al. (2021) Structure of the human marker of self 5-transmembrane receptor CD47. Nat. Commun. 12, 5218

---

# mmc1 (1)

# An anti-CD47 antibody binds to a distinct epitope in a novel metal ion-dependent manner to minimize cross-linking of red blood cells

Xiao Lu $^{1\#}$ , Ziyue Chen $^{2\#}$ , Chunyan Yi $^{1\#}$ , Zhiyang Ling $^{1\#}$ , Jing Ye $^{4\#}$ , Kaijian Chen $^{2}$ , Yao Cong $^{2}$ , Sonam Wangmo $^{4}$ , Shipeng Cheng $^{1}$ , Ran Wang $^{5}$ , Danyan Zhang $^{4}$ , Jiefang Xu $^{5}$ , Jichao Yang $^{4}$ , Liyan Ma $^{1}$ , Qing Duan $^{6}$ , Xiaoyu Sun $^{3*}$ , Jianping Ding $^{2,4*}$ and Bing Sun $^{1,4*}$

$^{1}$ Key Laboratory of Multi-Cell Systems, Shanghai Institute of Biochemistry and Cell Biology, Center for Excellence in Molecular Cell Science, University of Chinese Academy of Sciences, Chinese Academy of Sciences, Shanghai 200031, China.

$^{2}$ Key Laboratory of RNA Innovation, Science and Engineering, Shanghai Institute of Biochemistry and Cell Biology, Center for Excellence in Molecular Cell Science, University of Chinese Academy of Sciences, Chinese Academy of Sciences, Shanghai 200031, China.

$^{3}$ Shanghai Institute of Infectious Disease and Biosecurity, Shanghai Medical College, Fudan University, Shanghai 200032, China.

$^{4}$ School of Life Science and Technology, ShanghaiTech University, Shanghai 201210, China.

$^{5}$ Division of Life Sciences and Medicine, University of Science and Technology of China, Hefei, China.

$^{6}$ TOT BIOPHARM Company Limited, Jiangsu 215024, China.

# Xiao Lu, Ziyue Chen, Chunyan Yi, Zhiyang Ling and Jing Ye contributed equally to this work.

* Corresponding authors:

Bing Sun: bsun@sibs.ac.cn; Jianping Ding: jpding@sibcb.ac.cn; Xiaoyu Sun:

sunxiaoyu@fudan.edu.cn;

![](images/7f5ea1d3accff8af33d0631b6028f721ba70018c763bbcc93a856070c7ededc6.jpg)  
A

![](images/2fadf0488042c014437335211eb9599f009eaba8f28080e3df8ee3e6fd31dc41.jpg)  
B

![](images/e81d0eab1f55867d3018b1460017c2f91ecd44553a6da816d1152f52296ec494.jpg)  
C

![](images/cfb61c8cb577a43610d3e766c1c0016e1671ce03b2b2f5440823e321ac886b23.jpg)  
D

E   

<table><tr><td></td><td>H3L1</td><td>H3L2</td><td>H3L3</td><td>H4L1</td><td>H4L2</td><td>H4L3</td><td>1C8</td></tr><tr><td>\( EC_{50} \) μg/ml</td><td>0.1089</td><td>0.1411</td><td>0.1254</td><td>0.1319</td><td>0.1446</td><td>0.1605</td><td>0.1759</td></tr><tr><td>\( IC_{50} \) μg/ml</td><td>2.105</td><td>3.368</td><td>2.426</td><td>2.995</td><td>3.088</td><td>1.788</td><td>2.252</td></tr></table>

![](images/a96088a334d50add9f76ea5872633130e25e371f7d2b8f5a2a0c9672aacd344e.jpg)  
F

![](images/1073fcd8fd8f6759811bf9cdf09265df488b60cfe7ea8477cf7759a698b07678.jpg)  
G

![](images/6cef9c7a4c92aa48db9d9d53ff103ce93d339bab4b9eb6be498ae5271eb36aae.jpg)  
H   
|

![](images/db778127fbc4a265f921cb6eacbd84c8d8f699d917f882ccca5530c93d0081c1.jpg)  
J

![](images/50b02d7fe84d041271f854f26804dfcf2109f8b1655110cbc27147897032ad1b.jpg)

![](images/70c5ea59d6757d632bc8f619e7d066b0e113be007980d657149e3cefa8ffbcb0.jpg)  
K   
L

![](images/6a6c8b60f5d8ed0f2c562b533a6175817897fd98e435829689f208a7a55d99b7.jpg)  
M

![](images/07db69b78d1f2f8f0c3930a092129a310fd2dd7482c729cf6a9efb3fe8c0e9b1.jpg)

N   

<table><tr><td rowspan="2">Antibodies</td><td colspan="2">1C8</td><td colspan="2">H3L1</td><td colspan="2">H3L3</td><td colspan="2">H4L1</td><td colspan="2">H4L3</td></tr><tr><td>HuCD47 ECD</td><td>CyCD47 ECD</td><td>HuCD47 ECD</td><td>CyCD47 ECD</td><td>HuCD47 ECD</td><td>CyCD47 ECD</td><td>HuCD47 ECD</td><td>CyCD47 ECD</td><td>HuCD47 ECD</td><td>CyCD47 ECD</td></tr><tr><td>\( K_d \) (M)</td><td>3.82E-09</td><td>8.84E-09</td><td>2.59E-08</td><td>/</td><td>6.76E-09</td><td>1.07E-08</td><td>5.25E-09</td><td>1.77E-08</td><td>1.49E-08</td><td>/</td></tr><tr><td>\( K_{on} \) (1/Ms)</td><td>1.33E+04</td><td>1.02E+04</td><td>6.08E+03</td><td>/</td><td>9.35E+03</td><td>7.96E+03</td><td>6.92E+03</td><td>3.93E+03</td><td>8.75E+03</td><td>/</td></tr><tr><td>\( K_{off} \) (1/s)</td><td>5.08E-05</td><td>9.03E-05</td><td>1.57E-04</td><td>/</td><td>6.32E-05</td><td>8.54E-05</td><td>3.63E-05</td><td>6.96E-05</td><td>1.30E-04</td><td>/</td></tr><tr><td>Relative</td><td>/</td><td>/</td><td>6.78</td><td>/</td><td>1.77</td><td>1.2</td><td>1.37</td><td>2</td><td>3.9</td><td>/</td></tr></table>

Figure S1 The activity of humanized antibodies. A-B Binding activity of the first round of humanized antibodies to the HuCD47 ECD. C Binding activity of the second round of humanized antibodies to the HuCD47 ECD. D Neutralizing activity of the second round of humanized antibodies against the HuCD47 ECD. E The $EC_{50}$ and $IC_{50}$ values of the humanized antibodies. F-M Fitting curves of the binding kinetics of humanized antibodies to the HuCD47 ECD (F-J) and the CyCD47 ECD (K-M), which were evaluated by the “1:1 Langmuir binding model” with an R2 value $\geqslant0.95$ by Fortebio Data Analysis 7.0 software. N Affinities ( $K_{d}$ values) of the humanized antibodies for the HuCD47 ECD and the CyCD47 ECD. The results in (A-D) are presented as the means $\pm$ SD. Data are representative of two independent experiments.

A   

<table><tr><td rowspan="2">Relative EC50</td><td colspan="2">CCRF-CEM</td><td colspan="2">Raji</td><td colspan="2">HAEC</td><td colspan="2">RPTEC</td><td colspan="2">RBC</td></tr><tr><td>Hu1C8</td><td>Hu5F9-G4</td><td>Hu1C8</td><td>Hu5F9-G4</td><td>Hu1C8</td><td>Hu5F9-G4</td><td>Hu1C8</td><td>Hu5F9-G4</td><td>Hu1C8</td><td>Hu5F9-G4</td></tr><tr><td>CCRF-CEM</td><td>1.00</td><td>1.00</td><td>0.68</td><td>0.42</td><td>1.75</td><td>0.05</td><td>10.39</td><td>2.27</td><td>36.27</td><td>7.45</td></tr><tr><td>Raji</td><td>1.47</td><td>2.39</td><td>1.00</td><td>1.00</td><td>2.57</td><td>0.13</td><td>15.29</td><td>5.43</td><td>53.35</td><td>17.83</td></tr><tr><td>HAEC</td><td>0.57</td><td>18.33</td><td>0.39</td><td>7.67</td><td>1.00</td><td>1.00</td><td>5.94</td><td>41.67</td><td>20.74</td><td>136.67</td></tr><tr><td>PRTEC</td><td>0.10</td><td>0.44</td><td>0.07</td><td>0.18</td><td>0.17</td><td>0.02</td><td>1.00</td><td>1.00</td><td>3.49</td><td>3.28</td></tr><tr><td>RBC</td><td>0.03</td><td>0.13</td><td>0.02</td><td>0.06</td><td>0.05</td><td>0.01</td><td>0.29</td><td>0.30</td><td>1.00</td><td>1.00</td></tr></table>

![](images/27c771ace4f6db8a5566141ee4cfc0df08942418800bbba308602df7b365cb6f.jpg)  
B

![](images/291db0363508c51e15a8ab37853bd46a20486e524c12ad1e030184bc78709cf0.jpg)  
C   
D

![](images/427b077a81d4168b2647899399292a8dbad6fd41cf26e2053ec352cedd5c562e.jpg)  
Figure S2 The binding activity of Hu1C8 to different cells. A The relative binding activity of Hu1C8 to different normal and tumour cells. B-D Haemagglutination activity of Hu1C8 on human RBCs from different donors.

![](images/5173cdea31d433b5efe9b9fb258629174a159bd28d8c610e4895dba08ea5d252.jpg)  
A

![](images/4b4246cd93540559deaa174b335e9066cf97225c8c3659d26257f1d86811b752.jpg)  
B

![](images/53beab7a7c32c14add0460ac9dd982dd7315f06657bc5c8bda4dab734d74f8ab.jpg)  
C

![](images/76ae8dfe18364f8990455a78d2e25bef37cb4327eb24478ea326e0d761a0f065.jpg)  
D

![](images/e3bf5e0d87543a807eafeab20c516fcff3bcff52b95c9a35461d2d5d630dda66.jpg)  
E

![](images/9ac771f7dd8e80a9ffac9d7c435ed3999f5571bc0fdb51e987bcceb92400acfd.jpg)  
F

![](images/a6744086a6f8886e8d0c1928c7ee54eabfda4db254e5f0645068c09490bad1d3.jpg)  
G   
Figure S3 Hu1C8 inhibited tumour growth in a dose-dependent manner in vivo. A-C The curves of tumor volume under different treatment regimens (n=6-7 mice per group). CR, Complete Response.

![](images/83e9f24a2af4832f5b08371aff860ba1b9893b8656ba70159414ceca652d3dcf.jpg)  
Figure S4 Effect of different alanine variants of the HuCD47 ECD on the inhibition rate of antibody binding. The inhibition rate was calculated as the HuCD47 ECD value minus the mutant well value divided by the HuCD47 ECD value.

![](images/2bf3d3385fd2790898a53351038e3e5ab1ac95a1df836ad4f7d4835ffdcf423c.jpg)

![](images/ee0bb7a8e16ec5a3fbe9edb44cb11f40f35882486865c0f33293c3e1bee070d3.jpg)

![](images/eb5071213b5e51a5c5be5fcb394c2eae05129cd1b4e39c45b7a419738389992d.jpg)

![](images/84c1afd2504edd9ec39f4cf2d0cadb83d1a3dd96a053f4843c48c62734fd6b66.jpg)

![](images/aef455b2d594098fc9644993378ffa28a9e297662cb2d84772f68d2d1ca4e82b.jpg)

![](images/3273d1613a1138c16cb3f299e3c1a090f40bd899f73bed855df145ec3c64f2ee.jpg)

![](images/79450e44313fb48fb643a0685cbadfba301329ddc7e078dcf6a66c421a9e1051.jpg)  
B6H2 Fab
(PDB code: 5TZU)

SIRPα
(PDB code: 2JJS)

Hu1C8 Fab (This study)

Hu5F9 diabody (PDB code: 5IWL)

![](images/d8c5f17b64f8da9fbf8d3e63e04515b84608c79c639cb76d53381f7f51acd6eb.jpg)  
C47B222 Fab (PDB code: 5TZ2)   
C47B161 Fab (PDB code: 5TZT)

![](images/b3fba150e4f63151b67d2307b01b44e123dc42cd5f4c5a76a27cde333ce8430e.jpg)

![](images/b279a2d2a771949ce765c4bd2bc45f85055bbb945dce706e91c062cbade983ec.jpg)  
BC31M5 Fab
(PDB code: 7WN8)

![](images/2e93bf6f78d5497eba9cb33eccc184cd5fc4663e1568dc3f049c096597d788d3.jpg)

![](images/128bcd3388814a85420889301067c9532d9f2e82c0ef13c80dd099f2c26c95ad.jpg)  
6MW3211 Fab (PDB code: 7XJF)   
Figure S5 Structural comparison of the CD47-SIRPα $^{1}$ , CD47-Hu1C8 and other CD47-antibody complexes $^{2, 3, 4, 5}$ . The CD47 ECD, SIRPα and the Fab or diabody of different antibodies are shown in gray, purple and cyan, respectively. The epitope residues on the CD47 ECD are highlighted in red. The upper panel and the lower panel show two different orientations of the CD47 ECD.

Supplementary Table 1. Crystallographic diffraction data and structure refinement statistics   

<table><tr><td></td><td>Hu1C8 Fab-CD47 ECD</td></tr><tr><td colspan="2">Data collection</td></tr><tr><td>Wavelength (Å)</td><td>0.9792</td></tr><tr><td>Resolution (Å)</td><td>50.0-2.49 (2.58-2.49)a</td></tr><tr><td>Space group</td><td>P 1</td></tr><tr><td colspan="2">Cell parameters</td></tr><tr><td>a, b, c (Å)</td><td>45.22, 79.93, 92.75</td></tr><tr><td>α, β, γ(°)</td><td>112.51, 96.61, 103.16</td></tr><tr><td>Observed reflections</td><td>108,105</td></tr><tr><td>Unique reflections (I/σ(I) &gt; 0)</td><td>38,120 (2572)</td></tr><tr><td>Average redundancy</td><td>2.8 (2.4)</td></tr><tr><td>Average I/σ(I)</td><td>8.1 (2.8)</td></tr><tr><td>Completeness (%)</td><td>99.6 (99.2)</td></tr><tr><td>Rmerge(%)b</td><td>16.3 (33.5)</td></tr><tr><td>CC1/2</td><td>0.955 (0.858)</td></tr><tr><td colspan="2">Refinement and structure model</td></tr><tr><td>Reflections (Fo≥0σ(Fo))</td><td>36,286 (2571)</td></tr><tr><td>Working set</td><td>34,384 (2436)</td></tr><tr><td>Test set</td><td>1902 (135)</td></tr><tr><td>Rwork/Rfree(%)c</td><td>21.5/26.6</td></tr><tr><td>No. of atoms</td><td>8565</td></tr><tr><td>Protein</td><td>8323</td></tr><tr><td>Ligands</td><td>70</td></tr><tr><td>Solvent</td><td>172</td></tr><tr><td>Wilson B-factor (Å2)</td><td>41.02</td></tr><tr><td>Average B-factor (Å2)</td><td>45.50</td></tr><tr><td>Protein</td><td>45.53</td></tr><tr><td>Ligands</td><td>44.86</td></tr><tr><td>Solvent</td><td>44.31</td></tr><tr><td colspan="2">RMS deviations</td></tr><tr><td>Bond length (Å)</td><td>0.009</td></tr><tr><td>Bond angles (°)</td><td>1.06</td></tr><tr><td colspan="2">Ramachandran plot (%)</td></tr><tr><td>Favoured</td><td>95.22</td></tr><tr><td>Allowed</td><td>4.78</td></tr><tr><td>Outliers</td><td>0</td></tr></table>

$^{a}$ Numbers in parentheses refer to the highest resolution shell.   
$^{b}$ $R_{merge}=\sum_{hkl}\sum_{i}\left|I_{i}(hkl)_{i}-\langle I(hkl)\rangle\right|/\sum_{hkl}\sum_{i}I_{i}(hkl).$   
$^{c}$ R factor= $\left|\left|F_{o}\right|-\left|F_{c}\right|\right|/\left|F_{o}\right|$ .

# References

1. Hatherley D, Graham SC, Turner J, Harlos K, Stuart DI, Barclay AN. Paired receptor specificity explained by structures of signal regulatory proteins alone and complexed with CD47. Mol Cell 31, 266-277 (2008).   
2. Li Y, et al. A pH-dependent anti-CD47 antibody that selectively targets solid tumors and improves therapeutic efficacy and safety. J Hematol Oncol 16, 2 (2023).   
3. Pietsch EC, et al. Anti-leukemic activity and tolerability of anti-human CD47 monoclonal antibodies. Blood Cancer J 7, e536 (2017).   
4. Wang R, et al. Blockade of dual immune checkpoint inhibitory signals with a CD47/PD-L1 bispecific antibody for cancer treatment. Theranostics 13, 148-160 (2023).   
5. Weiskopf K, et al. CD47-blocking immunotherapies stimulate macrophage-mediated destruction of small-cell lung cancer. J Clin Invest 126, 2610-2620 (2016).