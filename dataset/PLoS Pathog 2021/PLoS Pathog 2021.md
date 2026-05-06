# ppat.1009543

![](images/8fb69625727ff6f6cb3dafb39da1821e1a8c4cf5fe87cd8308e00b4777ce2d8e.jpg)

Check for updates

![](images/8c31d45e2592971b7bcdb8da6b30fbc8bd3588496d77834f6869d4581cc78d7e.jpg)

# OPEN ACCESS

Citation: Aljedani SS, Liban TJ, Tran K, Phad G, Singh S, Dubrovskaya V, et al. (2021) Structurally related but genetically unrelated antibody lineages converge on an immunodominant HIV-1 Env neutralizing determinant following trimer immunization. PLoS Pathog 17(9): e1009543. https://doi.org/10.1371/journal.ppat.1009543

Editor: Katie J. Doores, King's College London, UNITED KINGDOM

Received: April 6, 2021

Accepted: September 1, 2021

Published: September 24, 2021

Copyright: This is an open access article, free of all copyright, and may be freely reproduced, distributed, transmitted, modified, built upon, or otherwise used by anyone for any lawful purpose. The work is made available under the Creative Commons CC0 public domain dedication.

Data Availability Statement: Coordinates and Structures factors have been deposited in the Protein Data Bank (PDB) under the PDB ID 6XLZ, 6VJN, 6WIT, 6WAS, and 6XSN for the antibody complexes.

Funding: This work was funded by the NIH HIV Vaccine Research and Design (HIVRAD) grant P01 AI104722 to M.P., G.B.KH., and R.T.W.; a Distinguished Professor grant (#2017-00968) from the Swedish Research Council to G.B.KH.; a

RESEARCH ARTICLE

# Structurally related but genetically unrelated antibody lineages converge on an immunodominant HIV-1 Env neutralizing determinant following trimer immunization

Safia S. Aljedani $^{1}$ , Tyler J. Liban $^{1}$ , Karen Tran $^{2}$ , Ganesh Phad $^{3a}$ , Suruchi Singh $^{1}$ , Viktoriya Dubrovskaya $^{2}$ , Pradeepa Pushparaj $^{3}$ , Paola Martinez-Murillo $^{3ab}$ , Justas Rodarte $^{1}$ , Alex Mileant $^{4}$ , Vidya Mangala Prasad $^{4}$ , Rachel Kinzelman $^{4}$ , Sijy O'Dell $^{5}$ , John R. Mascola $^{5}$ , Kelly K. Lee $^{4}$ , Gunilla B. Karlsson Hedestam $^{3}$ , Richard T. Wyatt $^{2,6}$ , Marie Pancera $^{1*}$

1 Fred Hutchinson Cancer Research Center, Vaccine and Infectious Disease Division, Seattle, Washington, United States of America, 2 The Scripps Research Institute, IAVI Neutralizing Antibody Center, La Jolla, California, United States of America, 3 Department of Microbiology, Tumor and Cell Biology, Karolinska Institutet, Stockholm, Sweden, 4 Department of Medicinal Chemistry, University of Washington, Seattle, Washington, United States of America, 5 Vaccine Research Center, National Institute of Allergy and Infectious Diseases, National Institutes of Health, Bethesda, Maryland, United States of America, 6 Department of Immunology and Microbiology, The Scripps Research Institute, La Jolla, California, United States of America

a Current address: Institute for Research in Biomedicine, Università della Svizzera italiana, Bellinzona, Switzerland
b Current address: Center for Vaccinology, Department of Pathology and Immunology, Faculty of Medicine, Geneva University Hospitals, Geneva, Switzerland
* mpancera@fredhutch.org

# Abstract

Understanding the molecular mechanisms by which antibodies target and neutralize the HIV-1 envelope glycoprotein (Env) is critical in guiding immunogen design and vaccine development aimed at eliciting cross-reactive neutralizing antibodies (NAbs). Here, we analyzed monoclonal antibodies (mAbs) isolated from non-human primates (NHPs) immunized with variants of a native flexibly linked (NFL) HIV-1 Env stabilized trimer derived from the tier 2 clade C 16055 strain. The antibodies displayed neutralizing activity against the autologous virus with potencies ranging from 0.005 to 3.68 $\mu$ g/ml (IC $_{50}$ ). Structural characterization using negative-stain EM and X-ray crystallography identified the variable region 2 (V2) of the 16055 NFL trimer to be the common epitope for these antibodies. The crystal structures revealed that the V2 segment adopts a $\beta$ -hairpin motif identical to that observed in the 16055 NFL crystal structure. These results depict how vaccine-induced antibodies derived from different clonal lineages penetrate through the glycan shield to recognize a hypervariable region within V2 (residues 184–186) that is unique to the 16055 strain. They also provide potential explanations for the potent autologous neutralization of these antibodies, confirming the immunodominance of this site and revealing that multiple angles of approach are permissible for affinity/avidity that results in potent neutralizing capacity. The structural analysis reveals that the most negatively charged paratope correlated with the potency of the mAbs. The atomic level information is of interest to both define the means of autologous

Wenner-Gren Foundations fellowship to G.P.; NIH grants (R01 AI145055 and CHAVD UM1AI144462), Bill and Melinda Gates Foundation CAVD grant (OPP1084519), the IAVI Neutralizing Antibody Center to R.T.W.; NIH grant number R01 AI140868 to K.K.L.; R.K. was supported by NIH T32 AI007509, and A.M. was supported by NIH T32 GM007750. The funders had no role in study design, data collection and analysis, decision to publish, or preparation of the manuscript.

Competing interests: The authors have declared that no competing interests exist.

neutralization elicited by different tier 2-based immunogens and facilitate trimer redesign to better target more conserved regions of V2 to potentially elicit cross-neutralizing HIV-1 antibodies.

# Author summary

NHPs immunizations with an HIV-1 immunogen (native-like tier 2 clade C 16055 strain) elicit potent HIV-1 tier 2 autologous polyclonal neutralizing antibodies. To understand the basis of the autologous neutralization, we determined structures of antibodies isolated from the vaccinated NHPs in complex with their epitopes. Our structural analysis reveals that the V2 hypervariable region, unique to 16055, is immunodominant and targeted by antibodies from diverse lineages. Additionally, vaccine-elicited V2 NAbs use different binding angles to avoid Env N-glycan shield and the more negatively charged paratope displays potent autologous neutralizing function. In summary, detailed analysis of how vaccine-elicited monoclonal antibodies interact with the target antigen provide valuable information for the design of immunogens aimed to elicit more broadly HIV-neutralizing antibodies. The use of cocktail/prime-boost sequential regimens that include a range of sequence variation combined with the removal/shielding of unwanted immunodominant epitopes will likely be needed to reach this goal.

# Introduction

The human immunodeficiency virus type 1 (HIV-1) is one of the major health challenges with 38 million cases worldwide [1,2]. The numerous HIV-1 strains are classified into four groups: M, N, O, and P, based on their zoonotic transmission history [3,4]. Group M is responsible for the majority of HIV-1 infections worldwide and is further divided into at least nine genetically distinct clades: A, B, C, D, F, G, H, J, K, and circulating recombinant form (CRFs) based on their sequence phylogenies [1,5]. The highest prevalence is in Southern Africa, India, and Ethiopia (clade C), which total $46\%$ of the HIV-1 infections worldwide. Therefore, an HIV-1 vaccine aimed to protect against transmission of clade C variants is a prioritized goal [1].

To provide protective immunity against the diverse array of HIV-1 strains circulating in the human population, broadly neutralizing antibodies (bNAbs) targeting the conserved regions of the variable HIV-1 envelope glycoprotein (Env) spike are needed. HIV-1 Env, the target of bNAbs, is a heterotrimeric glycoprotein located at the surface of the virus $[6]$ . So far, a vaccine capable of eliciting such responses has proven challenging due to the numerous immune escape properties the functional HIV-1 Env spike has evolved, including high antigenic diversity, heavy N-linked glycosylation, conformational masking and quaternary packing that occludes efficient antibody access to cross-conserved determinants $[7–13]$ . Nonetheless, an HIV-1 vaccine against diverse isolates and in particular clade C strains that cause most disease has been the focus of many studies $[4,14–16]$ .

Several designs of stabilized soluble Env trimers that mimic the functional viral spike were generated for clinical evaluation and vaccine development once near-atomic level structure of Env was obtained $[8,17–23]$ . A cleavage-independent near-native soluble Env mimic called native flexibly linked (NFL) trimer was successfully engineered for the clade C strain 16055 and its structure was determined $[18,19,24]$ . Recent studies reported that immunization of rhesus macaques with the stabilized 16055 NFL TD CC “I201/A433C” induced serum antibody

responses capable of neutralizing the 16055 autologous tier 2 virus. Furthermore, mAbs that mediated this activity were isolated and shown to bind a highly variable epitope determinant in the Env V2 region, as determined by alanine scanning mutagenesis and differential adsorption [25,26].

To further understand the immune response to the stabilized clade C 16055 immunogen following different immunization strategies in NHPs, we characterized mAbs from different immunization groups and determined their interactions with their epitope at low and high resolution, using negative stain EM (nsEM) and/or X-ray crystallography, respectively. Interestingly, all the NAbs recognized the same neutralizing hypervariable V2 loop but use different V genes, reflected in their differences in chemistry (electrostatic potential) and different angles of approach. This indicates that the polyclonal immune response favors these immunodominant epitopes, which are unique to the strain used for immunogen design. Our structural analysis suggests that careful analysis of both the sequence and structure of immunogens should be taken into account for next generation vaccine design: this immunodominant loop could be deleted or glycan-masked in priming immunizations to potentially shift neutralizing responses to more conserved determinants and more efficiently elicit cross-neutralizing antibodies.

# Results

# Immunization with native-like tier 2 Clade C NFL trimers elicit potent tier 2 autologous neutralizing antibodies

We have shown previously that the well-ordered, stabilized NFL Env trimer $[19]$ elicited HIV-1 autologous tier 2 neutralizing Abs in NHP $[25,26]$ . Here, we analyzed mAbs isolated from different immunization strategies with variants of the NFL Env-stabilized trimer in Chinese rhesus macaques (Macaca mulatta) to better understand the specificity of the elicited immune response. The animals were immunized at week 0, 4 and 12 (Fig 1A). Group A was immunized with 16055 NFL trimers conjugated to liposomes $[25]$ , group B was immunized with soluble 16055 NFL trimers with glycans at N276, N301, N360 and N463 deleted (degly 4 ( $\Delta$ 276, $\Delta$ 301, $\Delta$ 360, and $\Delta$ 463)) and group C was immunized with soluble 16055 degly 4 trimers at week 0 and 4 and boosted with the 16055 NFL with glycans restored (wild type, WT) at week 12 (Fig 1B). Two weeks after the third immunization, samples were collected. Plasma neutralization assays indicated that animals in all 3 groups developed tier 2 16055 autologous titers (S1 Fig).

We used single memory B cell sorting to isolate mAbs from animals that showed the highest serum neutralization: 3 mAbs from group A animal D11 (D11A.F2, D11A.B5, and D11A.F9, already reported elsewhere [25]), 3 mAbs from group B animal D15 (D15.SF6 and D15.SD7) and animal D16 (VD16.2C10); and 5 mAbs from group C animal D19 (D19.PA8 and D19.PD8) and animal D20 (VD20.1C7, VD20.1F9 and VD20.5A4) using 16055 NFL trimer probes. Neutralization against 16055 pseudovirus was assessed with potencies ranging from 0.005–~4 $\mu$ g/ml (Fig 1C and 1D).

All D11A antibodies share the same heavy chain germline VH4_3T_S3452 and JH4*01 genes, as well as the same light chain germline VL6-2*01_S6633 and JL2*01 genes (Fig 1E). Antibodies isolated from animal D15, D15.SF6 and D15.SD7 share the same heavy and light chain germline genes: IGH1_2L, JH4*01, IGLV6-2*01 and JL2*01 (Fig 1E). D19-isolated antibodies, D19.PA8 and D19.PD8, use different heavy chains germline genes, VH3_2T_S2563, JH5-2*02 and VH3_4A_S7053, JH4*01, respectively. D19.PA8 shares the same light chain germline genes IGLV6-2*01 and JL2*01 as the D15-isolated mAbs described above, while D19.PD8 uses the light chain germline genes lib5lambda_1 and JL1*01. VD16.2C10 uses the VH4_5H_S2253, JH4*02 or JH5*02, lib4kappa_12 and JK2*01 germline genes. D20-isolated mAbs are clonally related and use the VH4.11_S9546, JH 5–1*01_S8786, lib4kappa_12 and JK2*01 or JK4*01

![](images/4765b9defd51af26295bddee4bd908e1869bfe7b9910ea29cdca285dffdefb38.jpg)  
A   
C

![](images/5069b6b885be98730320c0e50dd340cd2332773dcad47fb10c7b605f6213db83.jpg)

B

![](images/1d0204f6d9ec8c26955022eff7f0be6d870d744df54f58b92a84749374ca79b0.jpg)  
Fig 1. Immunization with 16055 Clade C NFL variants in NHP and autologous neutralization from vaccine-elicited mAbs. (A) Overview of the immunization and sampling of the rhesus macaques. (B) Immunization strategies and groups. (C) Example of B-cell sorting with 16055 NFL probes to identify mAbs with potent tier 2 autologous neutralization. (D) Neutralization activity ( $IC_{50}$ ) of mAbs isolated from each group. (E). Antibodies isolated from various immunization trials and germline lineages. $^{\#}$ , $^{*}$ , $\dagger$ Clonal variants.

D

Neutralization Activity IC $_{50}$ (μg/ml)   

<table><tr><td>Animal ID</td><td>Time point</td><td>mAbs</td><td>16055 WT</td></tr><tr><td rowspan="3">D11</td><td rowspan="3">Post-3</td><td>D11A.B5#</td><td>3.68</td></tr><tr><td>D11A.F2#</td><td>2.49</td></tr><tr><td>D11A.F9#</td><td>3.28</td></tr><tr><td rowspan="2">D15</td><td rowspan="2">Post-3</td><td>D15.SF6*</td><td>0.25</td></tr><tr><td>D15.SD7*</td><td>0.13</td></tr><tr><td>D16</td><td>Post-3</td><td>VD16.2C10</td><td>0.03</td></tr><tr><td rowspan="2">D19</td><td rowspan="2">Post-3</td><td>D19.PA8</td><td>1.93</td></tr><tr><td>D19.PD8</td><td>0.28</td></tr><tr><td rowspan="3">D20</td><td rowspan="3">Post-3</td><td>VD20.1C7</td><td>0.11</td></tr><tr><td>VD20.1F9†</td><td>0.03</td></tr><tr><td>VD20.5A4†</td><td>0.005</td></tr></table>

E   

<table><tr><td colspan="2">Group NHP ID</td><td>V1V2 mAbs</td><td>VH</td><td>JH</td><td>HCDR3</td><td>%VH SHM (nt)</td><td>%VH SHM (aa)</td><td>VL/VK</td><td>JL/JK</td><td>LCDR3</td><td>%VL/VK SHM (nt)</td><td>%VL/VK SHM (aa)</td></tr><tr><td rowspan="3">A</td><td>D11</td><td>D11A.B5#</td><td>4_3T_S3452</td><td>4*01</td><td>ARPYCAIGRCYES</td><td>4.8</td><td>8.3</td><td>VL6-2*01_S6633</td><td>JL2*01</td><td>QSSDDSYNWV</td><td>1.7</td><td>3.1</td></tr><tr><td>D11</td><td>D11A.F2#</td><td>4_3T_S3452</td><td>4*01</td><td>ARPYCPGSACYDS</td><td>5.5</td><td>10.4</td><td>VL6-2*01_S6633</td><td>JL2*01</td><td>QSADDSYNWV</td><td>2.4</td><td>3.1</td></tr><tr><td>D11</td><td>D11A.F9#</td><td>4_3T_S3452</td><td>4*01</td><td>AGPFCPGGRCYDS</td><td>5.9</td><td>12.5</td><td>VL6-2*01_S6633</td><td>JL2*01</td><td>QSADDNYNWI</td><td>2.7</td><td>6.1</td></tr><tr><td rowspan="3">B</td><td>D15</td><td>D15.SF6*</td><td>1_2L</td><td>4*01</td><td>ATDHREDGPTYFSGVQWVPFRF</td><td>4.9</td><td>8.3</td><td>VL6-2*01</td><td>JL2*01</td><td>QSPDGRYNRV</td><td>1.3</td><td>4</td></tr><tr><td>D15</td><td>D15.SD7*</td><td>1_2L</td><td>4*01</td><td>ATDHREDGPTYFSGVQWVPFRF</td><td>3.7</td><td>7.3</td><td>VL6-2*01</td><td>JL2*01</td><td>QSPDGRYNRV</td><td>1.3</td><td>4</td></tr><tr><td>D16</td><td>VD16.2C10</td><td>VH4_5H_S2253</td><td>4*02 or 5*02</td><td>ARALWSGYYVWIDV</td><td>9.1</td><td>17.5</td><td>lib4kappa_12</td><td>JK2*01</td><td>LQDYATPYS</td><td>3.9</td><td>9.7</td></tr><tr><td rowspan="5">C</td><td>D19</td><td>D19.PA8</td><td>3_2T_S2563</td><td>5-2*02</td><td>ARAPVWTGYTSLDV</td><td>3.4</td><td>8.3</td><td>VL6-2*01</td><td>JL2*01</td><td>QSSDDNFNWV</td><td>4</td><td>11.1</td></tr><tr><td>D19</td><td>D19.PD8</td><td>3_4A_S7053</td><td>4*01</td><td>ARDGVGSCSVGVCYTPFDY</td><td>4</td><td>10.2</td><td>lib5lambda_1</td><td>JL1*01</td><td>QSLDSSGNHYI</td><td>2.6</td><td>6.2</td></tr><tr><td>D20</td><td>VD20.1C7</td><td>4.11_S9546</td><td>5-1*01_S8786</td><td>ARGAWSGYYSWFDV</td><td>4.7</td><td>11.5</td><td>lib4kappa_12</td><td>JK4*01</td><td>LQDFTPPFT</td><td>3.2</td><td>5.4</td></tr><tr><td>D20</td><td>VD20.1F9†</td><td>4.11_S5664</td><td>5-1*01_S8786</td><td>ARGLWTGYFSWLDV</td><td>2</td><td>4.2</td><td>lib4kappa_12</td><td>JK2*01</td><td>LQDYSTPYS</td><td>2.5</td><td>5.4</td></tr><tr><td>D20</td><td>VD20.5A4†</td><td>4.11_S5664</td><td>5-1*01_S8786</td><td>ARGLWSGYFFWFDV</td><td>5.4</td><td>10.4</td><td>lib4kappa_12</td><td>JK2*01</td><td>LQDYATPYS</td><td>2.1</td><td>3.2</td></tr></table>

#,*,† Clonal variants

https://doi.org/10.1371/journal.ppat.1009543.g001

germline genes [26] (Fig 1E). The somatic hyper mutation (SHM) levels in VH and VL range from 4.2–17.5% and 3.1–11.1% at the residue (aa) level, respectively (Fig 1E) [27].

# Vaccine-elicited antibodies interact with the V2b hypervariable region

Cross-competition binding analysis between the NHP neutralizing mAbs and known bNabs targeting different Env regions indicated that they all generally mapped to the V2 apical region of the 16055 NFL trimer while also displaying complete self- and cross-inhibition, assigning them to the same competition group (S1B Fig). Binding to 16055 gp120 constructs containing

mutations in the V1/V2 loops confirmed specificity to the V2 region (S1C Fig). Epitope specificity was further mapped by neutralization sensitivity against a panel of 16055 pseudovirus mutants with residues along the 16055 V2 mini-loop (i.e., $^{182}$ VPLEEERKGN $^{187}$ ) mutated to alanine, or N187 mutated to glutamine (S1D Fig). The focused alanine scan confirmed dependence to the V2 hypervariable region as point mutants between residues V182 and K186C abrogated neutralization activity, while removal of the N187 glycan enhanced potency of the NHP mAbs (S1D Fig).

# Structural basis for HIV-1 tier 2 autologous neutralization

To understand the molecular basis for the tier 2 autologous neutralization from the isolated mAbs, we used a combination of nsEM and X-ray crystallography. To increase our chances of obtaining structural information, we used variational crystallography [28] where antigen binding fragments (Fabs) from a select number of antibodies complexed with 16055 NFL trimer, a scaffolded 16055 V1V2-1FD6 [29] and a 16055 V2b peptide [25] were purified and used for crystallization. Below we described the high-resolution structures we obtained which are the focus of our analysis.

D11A mAb structural characterization. The nsEM of 16055 NFL trimer in complex with D11A.F9 and 35022 Fab [30] confirmed that the D11A.F9 approached its epitope located at the apex of the HIV-1 trimer horizontally, or parallel to the viral membrane (Fig 2A), consistent with a previous study which showed that D11A.F9 bound V2 parallel to membrane [25]. D11A.F9 Fab crystals were obtained in complex with 16055 NFL trimer and 35022scFv [19,31,32], which diffracted X-ray to $6.5\AA$ . The low-resolution structure fitted well in the nsEM 3D reconstruction, confirming the horizontal angle of approach (Fig 2A).

Crystals of D11A.F2 and D11A.B5 were also obtained in complex with a 16055 V2 peptide, named here V2b peptide, $^{178}$ RLDIVPLEEERKGNSSKYRLINC $^{196}$ (numbering follows HXBc2 [33]), which diffracted X-rays to 2.8 Å and 2.0 Å resolution, respectively (S1–S3 Tables). In both structures, the V2b peptide structure was fully resolved (Fig 2B and 2C) and adopted the same conformation as seen in the 16055 NFL trimer structure (RMSD of 1.1 Å and 0.8 Å over 17 and 16 Cα atoms, respectively) [18]. The high-resolution structures indicated that both D11A.F2 and D11A.B5 bind mainly to the 16055 V2 region, of which residues $^{185}$ EEER $^{186A}$ appear unique to the 16055 strain (Fig 2B and 2C). The D11A.F2 antibody buries ~ 774 Å $^{2}$ of the V2b peptide, with ~701 Å $^{2}$ in the V2 region and ~73 Å $^{2}$ in Strand D [19,29] (Figs 2B and S2). Similarly, D11A.B5 buries ~ 725 Å $^{2}$ of the V2b peptide, with ~674 Å $^{2}$ in the V2 region and ~51 Å $^{2}$ in Strand D (Figs 2C and S3). We note that in both crystal structures, a shorter region of another V2b peptide appears to make additional interactions with D11A.F2 and D11A.B5 (S2 Fig), which we believe are crystallization artifacts. Since both the nsEM data and low-resolution crystal structure of D11A.F9 with 16055 NFL identified the hypervariable region V2 to be the epitope for D11A antibodies, we believe these additional contacts are not biologically relevant but the results of crystallization artifacts.

D15.SD7, D19.PA8 and VD20.5A4 mAb structural characterization. Crystals of D15. SD7, D19.PA8 and VD20.5A4 with the scaffolded 16055 V1V2-1FD6 were obtained and dif-fracted X-rays to resolution of 2.8 Å, 2.0 Å, and 2.8 Å, respectively (Figs 2D–2G and S1, S4–S6 Tables). The V1V2 structure adopts the same conformation as seen in the 16055 NFL trimer (RMSD of 0.9 Å, 0.6 Å, and 0.8 Å over 44, 39, and 41 Cα atoms, respectively), confirming that these antibodies recognize an epitope elicited by the trimer and that likely no induced-fit conformational changes were induced by the antibodies binding to the scaffolded V1V2 compared to the trimer. Our structural analysis indicated that there are two copies in the asymmetric unit of D15.SD7/1FD6-V1V2 and D19.PA8/1FD6-V1V2 structures (S4 and S5 Tables). We

![](images/b2095542341094d7577ef2d145e8048de8e434087356c90d8dac54ad514ad80c.jpg)  
A

![](images/695371c80e64fa6ed4a398e76fb3bc8906dff92c2655af61211126997d7b9e5a.jpg)  
Top view   
B

![](images/13f536fc30ff990990f93d08964e0a5df5b1856318eba135ec2f9d5e43212c1c.jpg)

![](images/1aaf191d6d95b80fed59d6f80ae31001147c2b098fb7e349793b421f9eaeb8aa.jpg)  
C

![](images/dc04b47ad6b61e2283abceb7cd7d9c55fe3e0ece7dd52005d006e101d9300259.jpg)  
D

![](images/62fb8d2504bcdb1e38a61833cf959a00620101aa40397b08286bc89f4a9270ec.jpg)  
E

![](images/5229a7afe63d062df59036feb6b83c86c3d170cd9c1092051eb590bc50bdde1f.jpg)  
F

![](images/8b24c755a386eb681ae7c468ae7ed8d67da97e93aadafc8f934aff212baabf38.jpg)  
G   
Fig 2. Vaccine-elicited antibodies recognize the V2 region of 16055 strain. (A) nsEM 3D reconstruction with low resolution crystal structure of D11A.F9 Fab (Heavy chain, dark green; Light chain, light green) and 35022 scFv (gray) in complex with 16055 NFL (gp120, yellow; gp41, light brown) shown in two different views. (B, C) Structures of D11A.F2 Fab (Heavy chain, sky blue; Light chain, cyan) and D11A.B5 Fab (Heavy chain, magenta; Light chain, light pink) bound to the V2b peptide (yellow). (D) Structures of D15.SD7 (Heavy chain, blue: Light chain, light blue), (E) D19.PA8 (Heavy chain, orange; Light chain, light orange) and (F) VD20.5A4 (Heavy chain, raspberry; Light chain, light raspberry) Fabs in complex with the 16055 V1V2-1FD6 scaffold. (B, C, D, E, F) Interacting residues are shown in sticks and glycans in green. Pie charts summarize the buried surface area (BSA) of the V2b and V1V2-1FD6. (G) Sequence of 16055 V1V2 highlighting the V2b peptide used for crystallization, the location of the V1, V2 and strands. Residues that contact the Mabs (within 5Å) are shown with asterisks underneath the sequence. N-linked glycosylation sites are shown in green.

https://doi.org/10.1371/journal.ppat.1009543.g002

observed clear density for three glycans in the gp120 V1V2 region at N156, N160 and N187 in one complex of D15.SD7/1FD6-V1V2, while the other complex in the asymmetric unit showed density for the N156 glycan only and thus chose the former for further analysis. Of note, D15. SD7 heavy chain showed some interactions with the 1FD6 scaffold (S4 Table), which we did not include in our analysis since they are not biologically relevant. Additionally, the 1FD6 scaffold was mostly disordered in the D19.PA8 and VD20.5A4 complex structures (Fig 2). We also note that strand C was mostly disordered in the D19.PA8/1FD6-V1V2 complex.

Similar to the D11A antibodies, D15.SD7, D19.PA8, and VD20.5A4 bind mostly the V2 hypervariable region. They bury $\sim824\AA^{2}$ , $\sim615\AA^{2}$ and $\sim522\AA^{2}$ of the V1V2, respectively (Fig 2D–2G), of which $\sim744\AA^{2}$ , $\sim603\AA^{2}$ and $\sim480\AA^{2}$ are in the hypervariable V2 region only.

In conclusion, the structural analyses support our previous alanine scanning results, which showed that $Glu^{185}$ , $Glu^{186}$ , $Glu^{186A}$ , $Arg^{186B}$ , and $Lys^{186C}$ mutations resulted in decrease or loss of neutralizing activities of D11A.F2 [25]. Indeed, all mAbs interact with the above-mentioned V2 residues (Fig 2 and S2–S6 Tables). We also observed additional interactions of all the mAbs with $Val^{182}$ , $Pro^{183}$ , $Leu^{184}$ , $Gly^{186D}$ , and $Asn^{187}$ (Fig 2G and S2–S6 Tables), with the light chains of D15.SD7 and D19.PA8 showing some contacts with the proximal N-acetylglucosamine (NAG) at residue $Asn^{187}$ (Fig 2D and 2E). We could not explain the slight difference in specificity at residues $Pro^{183}$ and $Leu^{184}$ described previously [26], which may highlight the importance of using both functional and structural analysis to provide a complete picture on the epitope and contact residues.

Finally, we also note that D15.SD7, D19.PA8 and VD20.5A4 make additional contacts in strand B, D and hypervariable V1 loop (Fig 2).

Since our high-resolution structures were solved with V2 peptide or V1V2 domain, we superimposed the above-described structures of mAb/V2b or V1V2 scaffold onto the structure of the 16055 NFL trimer (PDB ID: 5UM8) [19] by aligning the V2 or V1V2 region (S3 Fig). From this structural alignment, we would predict that some mAbs would have additional contacts with the trimer which were not observed in our structures, either because the residues were not present in the V2 peptide or V1V2 domains or because these residues were disordered or did not show interactions in the solved structure (S3 Fig). Interestingly, in the superposition, mAb VD20.5A4 did not show additional contacts to the 16055 NFL trimer.

# Polyclonal antibody response to a similar epitope

Since mAbs elicited from vaccination target the same V2 region, unique to 16055, but used diverse germline genes and their autologous neutralization potencies differed by almost a 1000-fold ( $IC_{50}$ ranging from 0.005 $\mu$ g/mL (VD20.5A4) to 3.68 $\mu$ g/mL (D11A.B5)) (Fig 1D), we looked at differences and similarities of the paratope at the molecular level (Fig 3). We also analyzed the antibodies' binding properties, including buried surface area (BSA), number of hydrogen bonds and salt bridges formed with the epitope, CDRH3 usage, electrostatics and angles of approach to decipher if some properties correlated with autologous neutralization potency (Figs 4–7).

The total BSA of D11A.F2 is $\sim 718\AA^2$ , that of D11A.B5 is $\sim 673\AA^2$ , that of D15.SD7 is $\sim 782\AA^2$ , that of D19.PA8 is $\sim 596\AA^2$ and $\sim 557\AA^2$ of VD20.5A4 surface area is buried upon binding to its epitope (Fig 3A-3E). We did not observe a correlation between the BSA of the paratope or that of the epitope with neutralization potency (Fig 4A and 4B). Indeed, VD20.5A4 is the most potent mAb but showed the least amount of BSA upon binding its epitope, indicating that in this case, precise targeting with a smaller epitope footprint might be relevant to potency.

The mAbs use all six complementary determining regions (CDRs) to bind their epitope, except for VD20.5A4 which does not use the CDRL2, and D15.SD7 which does not use the

![](images/eaad56a8dfa7733f2773e9e50aca7ea99fe6d6e73e45e5af900fb13010f0c893.jpg)

![](images/566c093d283d9aac36f18d0943397f5a7e125103590ddf97acbab7977bbc4992.jpg)

![](images/3a91b40ee4c6ddfee2c6991ba6a4b4fe991578893ff21fa2a200db8a4d84685d.jpg)

![](images/8fd8acbafef58fb013e3c214c6dd91486ed85966d74739327808bfb2d288c7b8.jpg)

![](images/71592965c1440e5de506238ac5870af8a55499c8dc169c99b77eacc1b9657ab8.jpg)

![](images/332620749346dd8eb978c0c9dc5c5a9d98815b220cdfb6cba8f6da32901a2967.jpg)  
Fig 3. Structural characterization of mAbs elicited from vaccination. Surface representations of (A) D11A.F2, (B) D11A.B5, (C) D15.SD7, (D) D19.PA8, and (E) VD20.5A4 Fabs. All mAbs are color coded as follows: CDR H1, chocolate; CDR H2, salmon; CDR H3, dark salmon; CDR L1, violet purple; CDR L2, deep purple and CDR L3, violet. The pie chart represents the relative contribution of each CDR loops to the total buried surface area of the paratope for each mAbs. (F) Sequence alignment of the mAbs to their germline genes with CDRs highlighted. Somatic hyper mutations (SHMs) are highlighted in red. Residues interacting with 16055 V2b peptide or 16055 V1V2 are shown as asterisks below the sequence (contact residues within 5 Å).

https://doi.org/10.1371/journal.ppat.1009543.g003

CDRH2. D11A, D15.SD7 and D19.PA8 mAbs also use part of the framework regions although these account for less than 6% of the total BSA (Fig 3). Finally, both heavy and light chains are similarly involved in the interactions, except for D15.SD7 and VD20.5A4 which use primarily the heavy chain (57% and 78% of the total BSA of the paratope, respectively), with the CDRH3 accounting for 56% and 50% of the total BSA of the paratope and 98% and 64% of the heavy chain BSA, respectively (Fig 3C, 3E and 3F). The CDRH3 length varies from 11 to 20 residues

![](images/ab4e1c651249580521587f8c5dfe6732a3ad996879e522ded7cf530d53d6d896.jpg)

![](images/5485cba1dc960db57f10c150e9ec9ca4c80f0e8383342d74928ef171bad9005d.jpg)

![](images/bfd6b0447a52d5c2c417d9c49e0fe3aae9ec3a29b712f42018da0d0c67588f7b.jpg)

![](images/063ab9e4643215aa3d61d7b2345ed16343b417560489981496d20eee1177519b.jpg)

![](images/18ccaad4ac6995237b4dded59bb9889acaf4a6894be7cec404e555fc77b0362b.jpg)

![](images/6d6db9f2351a371d2a1dcd1e59a636d21418720d3daf8051807b4a3b9b1ff892.jpg)  
Fig 4. MAbs binding properties and correlations with autologous neutralization potency. Correlation between autologous neutralization potency and (A) epitope surface area, (B) paratope surface area, (C) CDRH3 length, (D) relative contribution of the CDRH3 surface area in the paratope and (F) number of Hydrogen Bonds (HBs) and Salt Bridges (SBs). The lines indicate the fitted linear regression model with 95% confidence shown in shaded grey or color as indicated. The $r^{2}$ and p values are displayed. (E) Graph indicates number of HBs and SBs between the epitope/paratope with the different mAbs.

https://doi.org/10.1371/journal.ppat.1009543.g004

but no correlation with potency was observed although D15.SD7 used primarily its 20-amino-acid CDRH3 to interact with its epitope (Fig 4C). We then assessed the correlation between potency and the relative contribution of the CDRH3 over the paratope (BSA from the CDRH3 over the total paratope BSA), and determined that there was a trend to significance correlation

(Fig 4D). Indeed, it is interesting that the two mAbs that used most of their CDRH3 (in the context of our analysis, which only takes into account the V1V2 region and not the whole 16055 NFL trimer) proved to be the most potent autologous neutralizing mAbs.

All the mAbs used both germline and affinity matured V-gene residues in the interactions with their epitope, and within a clonally related family, some of the interacting residues differ, however it is unclear what the difference or role in the affinity maturation is regarding the overall potency (Fig 3F). We note that the D11A mAbs have an intradisulfide bond in the CDRH3, which appears to rigidify the loop causing it to be less involved in the interactions. Such disulfide bonds have been observed before in mAbs isolated in humans with HIV and HCV infections [34,35]. In these studies, the disulfide bonds were thought to be responsible for the antibodies' neutralization potencies by stabilizing the affinity matured antibodies.

We next assessed the number of hydrogen bonds (HBs) and salt bridges (SBs) formed in each paratope/epitope interaction (Fig 4E). D11A.F2 and D11A.B5 form 8 and 10 HBs with the V2b peptide, 6 and 8 of which interact directly with the hypervariable V2 region, respectively. In addition, D11A.F2 and D11A.B5 form 16 and 12 SBs with the V2b peptide, 12 and 8 of which interact with the hypervariable V2 region, respectively. D15.SD7 and D19.PA8 form 10 and 7 HBs with their epitope, all of which interact with the hypervariable V2 region. Moreover, D15.SD7 and D19.PA8 form 10 SBs with their epitope, all of them with the hypervariable V2 region. VD20.5A4 forms 7 HBs (6 with the hypervariable V2) and 3 SBs with the hypervariable V2 region (Fig 4E). In conclusion, the number of HBs and SBs between the paratope/epitope did not correlate with the mAbs autologous neutralization potency (Fig 4F).

To further understand the differences in the potency, we looked at the electrostatics of the epitope and paratopes (Fig 5). While the epitope is overall positively charged (Fig 5A and 5B), the paratopes showed different electrostatics [36], with VD20.5A4 being strongly negatively charged towards the center of its paratope (Fig 5C). It appears that the paratope electrostatic of VD20.5A4 is more compatible with the overall positively charged epitope, which could explain its increased potency.

Finally, to understand the various mAbs' angles of approach to their epitope on the 16055 NFL trimer, we used the superposition mentioned above of the bound structures of D11A.B5, D15.SD7, D19.PA8, and VD20.5A4 on 16055 NFL trimer by aligning the V2b region of each structure to the NFL trimer (PDB:5UM8) [19] and calculated their angles of approach from a side and top view (Fig 6). Our analysis suggests that D11A.B5, D15.SD7 and D19.PA8 mAbs approaches the V2 region with a similar angle (122–126°) from the side (lateral) (Fig 6A–6C, 6E and 6F) while VD20.5A4 approaches the 16055 NFL trimer slightly from above ( $\sim$ 114°) and rotated compared to the other mAbs (Fig 6D–6F). While all mAbs approach their epitope with the same angle as seen from a top view, D19.PA8 is tilted 5° from the others (Fig 6C, 6E and 6F).

In conclusion, our structural analysis suggests that the difference in potency between the vaccine-elicited mAbs that bind the same epitope is likely due to differences in electrostatics in the paratope and angle of approach of the mAbs. Additionally, the nature of the CDRH3 interaction with the epitope also plays a role in the mAbs potency.

# Autologous tier 2 antibodies target a partial hole in the glycan shield

N-linked glycans extensively shield the surface of the HIV Env [13,37] and this glycan shield is one of the reasons for Env's resistance to mAb-directed neutralization [38–40]. Here, to explore the role of the glycan shield, we superimposed the structures of the vaccine-elicited mAbs in complex with their epitope onto the high-resolution structure of 16055 NFL trimer with N-linked glycans [19] (Fig 7). Interestingly, it appears that the mAbs target a partial

![](images/09c0a9d504809d258c6c1f20aaa7d14100b11b640f9e08a528b17f18c25125fe.jpg)

![](images/88fae965d0751f43b118583bd9eb174ffc094ee2cdb365df1a60565326404770.jpg)  
Fig 5. Electrostatics surface representation of 16055 NFL and different mAbs. Electrostatics surface representation of (A) 16055 NFL and (B) V1V2 and V2 region zooms (top and side views). Epitopes are highlighted by dotted lines and some residues in V2 are shown in stick and labeled. (C) Electrostatics surface representation of the mAbs paratope. Residues forming the paratope are shown in sticks.

https://doi.org/10.1371/journal.ppat.1009543.g005

![](images/21089fa132d0e0fb232f330a237d07e0b51fe2b6d406664439501af4fe19bd47.jpg)  
A   
D11A.B5   
B   
D15.SD7

![](images/5151df8c05da2ded327f6f36bfe2761a9f16b50e926b86a20e84c4d050781646.jpg)

![](images/e2b917fefe20392d287701e40fd0703889516b7ffb98312402a13b435bdaf3fd.jpg)  
C   
D19.PA8   
D   
VD20.5A4

![](images/09a7693b8fb36e7f3ef8bce0c8797c6a9550aa42da3ad07c2a373b6532acea33.jpg)

![](images/b1337a156ca6c154b8d83359b8d98929de1b9aadcbd0598b05e45e1521499705.jpg)

![](images/53e957c12edbec80803f6947c688f4576cd2839e593bfea532778267773a28a8.jpg)

![](images/cf251f1b45a41df559308fe4060f0380e928ca221c6e5f7d5bea98d991e428b8.jpg)

![](images/537c36c729a7e9d6e10b19ef569b93ab93fced36a83ba271b89d8e758a3e2dde.jpg)

E

![](images/3d7dec94bb283f22c3285c2b9ddfa9ee29466cbb1809daec67c658442611fdc1.jpg)  
Fig 6. Vaccine-elicited mAbs target V2 region using a lateral approach with slightly different angles of approach. Side and top surface/cartoon representation of one gp120 (yellow)-gp41 (tan) 16055 NFL protomer with Fab bound: (A) D11A.B5 (pink), (B) D15.SD7 (blue), (C) D19.PA8 (orange) and (D) VD20.5A4 (raspberry) showing the angles of approach of each mAb. (E) Superimposition of gp120-gp41 16055 NFL protomer with D11A.B5 (pink), D15.SD7 (blue) and D19.PA8 (orange) onto VD20.5A4-bound gp120-gp41 protomer. (F) Summary of the mAbs angles of approach.

F

<table><tr><td>mAbs</td><td>Side Angle (°)</td></tr><tr><td>D11A.B5</td><td>126.3</td></tr><tr><td>D15.SD7</td><td>122.0</td></tr><tr><td>D19.PA8</td><td>126.2</td></tr><tr><td>VD20.5A4</td><td>113.8</td></tr></table>

<table><tr><td>mAbs</td><td>Top Angle (°)</td></tr><tr><td>D11A.B5</td><td>122.1</td></tr><tr><td>D15.SD7</td><td>123.2</td></tr><tr><td>D19.PA8</td><td>117.1</td></tr><tr><td>VD20.5A4</td><td>121.1</td></tr></table>

https://doi.org/10.1371/journal.ppat.1009543.g006

![](images/30ac4f2608cf04c9bb138b2fde660cee3f2d623106d05d3abbc691b1aae20977.jpg)  
A

![](images/1273390b8c43dc79bd98fb41bb4261dfff377f93e1ee87729e640d08169c5364.jpg)

![](images/3078ea527631a59ba6c63185f07fc32e5e1fcc44aa7c71c7c5af94ee77f5e5d5.jpg)  
B

C

![](images/b443ad5cd5e5f1f3efa49c2a2fb5f4ddec167cefa5f3633354646355a1f9ebd6.jpg)  
Fig 7. NHP Autologous tier 2 neutralizing antibodies target a hole in the HIV-1 glycan shield. (A) Side and top view surface representation of 16055 NFL (PDB:5UM8) with gp120 shown in yellow, V2 region in grey, gp41 in wheat and glycans shown in green spheres or color-coded and labeled. Arrows indicate mAbs' angle of approach. Epitopes targeted by the NHP mAbs are highlighted. (B) Side view and (C) Top view superpositions of the structures of D11A.B5, D15.SD7, D19.PA8 and VD20.5A4 onto the 16055 NFL trimer, showing how they access the glycan hole. Trimer and mAbs are shown in surface representation. Trimer is color coded as in (A) and mAbs as in Fig 3. (D) Effect of glycan removal surrounding the epitope on neutralization potency. Neutralization IC $_{50}$ values ( $\mu$ g/ml) shown with >10-fold differences highlighted in red.

D   

<table><tr><td></td><td>D11A.F9</td><td>D15.SD7</td><td>VD20.54A</td></tr><tr><td>WT</td><td>1.074</td><td>0.143</td><td>0.0023</td></tr><tr><td>N156A</td><td>0.365</td><td>0.090</td><td>0.0101</td></tr><tr><td>N187Q</td><td>0.054</td><td>0.002</td><td>0.0002</td></tr><tr><td>N197Q</td><td>0.015</td><td>0.001</td><td>0.0001</td></tr><tr><td>N360Q</td><td>0.206</td><td>0.028</td><td>0.008</td></tr><tr><td>N362A</td><td>0.387</td><td>0.131</td><td>0.004</td></tr><tr><td>N386A</td><td>0.013</td><td>0.011</td><td>0.001</td></tr></table>

https://doi.org/10.1371/journal.ppat.1009543.g007

glycan hole at the apex of the trimer formed by the long variable V2 sequence surrounded by glycans at position N156, N187, N197 and N386 (Fig 7A). The superposition also indicates that D11A, D15.SD7 and D19.PA8 mAbs will likely interact with glycans N197 and N386. The N-glycan at residue 197 appears to clash in the superposition, indicating that it must move out of the way to accommodate binding by these antibodies. No glycans appear to clash with trimer recognition by the VD20.5A4 antibody, which is in agreement with its slightly different angle of approach and smaller epitope footprint. The conserved N-linked glycosylation site at residue N187 in the variable V2 region makes minimal contacts with the light chains of D15. SD7 and D19.PA8 (Fig 2 and S4 and S5 Tables), since there is electron density for the first proximal NAG in some molecules of the asymmetric unit. We performed site directed mutagenesis to evaluate the effect of removing certain glycans on neutralization potency. In agreement with our structural observations, removal of glycan at position N386 enhanced the potency of D11A.F9 and D15.SD7 mAbs while there was no effect on VD20.5A4 neutralizing acitivity. Additionally, removal of glycans at N187 and N197 showed increased potency (>10 fold) for all mAbs tested (Fig 7D).

# Discussion

Revealing the molecular mechanisms by which vaccine-elicited antibodies target and neutralize the HIV-1 Env are invaluable to guide immunogen design and vaccine development $[41,42]$ . Our analysis shows that immunizations in macaques of a well-ordered 16055-based NFL trimer immunogen elicited mAbs that neutralize the autologous virus by targeting a gap in the dense glycan shield from which a small hypervariable V2 loop is antibody accessible. Germline gene analysis revealed that clonally distinct antibodies can target this same region with $\sim$ 1000-fold difference in potency. Interestingly, the most potent antibody, VD20.5A4 was not the most somatically hypermutated antibody. Our structural analysis indicates that the contribution of the CDRH3, electrostatics complementarity and angle of approach are likely responsible for the difference in potency between these mAbs. Of interest, VD20.5A4, which showed a smaller epitope footprint by targeting the epitope slightly more vertically than laterally compared to the others, also avoided most of the surrounding N-linked glycans. We can use the information collected here for immunogen “redesign” for more optimal targeting of relevant neutralization determinants. Although this loop is hypervariable in both length and sequence in each strain, it is likely often Ab-targeted $[43]$ , generating escape and hyper variability in humans $[44]$ . This may be similar in terms of a shield breach in the BG505 Env, resulting in a vaccine-elicited immunodominant autologous neutralization response to the BG505 in rabbits, directed to a relatively large “glycan hole” at N241/N289 present in those trimers $[45,46]$ . This is unlike the epitopes targeted by the broadly neutralizing antibodies which target conserved regions of Env (S4 Fig).

Other V2-directed antibodies have been reported and characterized by some as four epitope families (V2p, V2i, V2q, and V2qt) based on their cognate epitopes $[47,48]$ . Based on our analysis, it is unclear if the mAbs described here fit in any of these previously described families, although they appear to overlap with the V2i mAbs, which recognize a discontinuous epitope in V2 overlapping the $\alpha4\beta7$ integrin binding site $[49]$ . It is thus possible that the mAbs described here can effectively elicit Fc-mediated functions.

Here, we show that multiple clonally distinct antibodies elicited by 16055-based NFL trimers targeted a unique immunodominant V2 sequence. Interestingly, all antibodies recognize the conformation of this site as observed in the trimer context, even when co-crystallized with peptides or scaffolded V1V2. The V1V2 scaffold can sometimes adopt other conformations [50], indicating that the use of well-ordered native like trimer as immunogens is likely needed

to elicit mAbs that will bind such a conformation. The data suggest a potential means to better induce antibody neutralization breadth that would begin with structure-guided modification of strain-restricted but immunodominant gaps in glycan shielding. This testable process would involve either glycan-filling of holes in the shield or deleting or glycan-masking protruding loops to potentially shift responses toward more cross-conserved sites to better elicit cross-neutralizing responses to less immunogenic recessed determinants.

# Materials and methods

# Ethics statement

The animal work was conducted with the approval of the regional Ethical Committee on Animal Experiments (Stockholms Norra Djurförsöksetiska Nämnd). All animal procedures were performed according to approved guidelines.

# Animals

Female rhesus macaques (Macaca mulatta) of Chinese origin, 4–10 years old, were housed at the Astrid Fagraeus Laboratory at Karolinska Institutet. Housing and care procedures complied with the provisions and general guidelines of the Swedish Board of Agriculture. The facility has been assigned an Animal Welfare Assurance number by the Office of Laboratory Animal Welfare (OLAW) at the National Institutes of Health (NIH). The macaques were housed in pairs in 4 m $^{3}$ cages, enriched to give them possibility to express their physiological and behavioral needs. They were habituated to the housing conditions for more than 6 weeks before the start of the experiment and subjected to positive reinforcement training in order to reduce the stress associated with experimental procedures. All immunizations and blood samplings were performed under sedation with ketamine 10–15 mg/kg intramuscularly (i.m.) (Ketaminol 100 mg/ml, Intervet, Sweden). The macaques were weighed at each sampling. All animals were confirmed negative for simian immunodeficiency virus (SIV), simian T cell lymphotropic virus, simian retrovirus type D and simian Herpes B virus.

# Immunization and sampling

Rhesus macaques were divided into groups and inoculated with variants of NFL HIV-1 Env trimers derived from the tier 2 clade C 16055 strain [19,25]. Group A was inoculated with liposome-conjugated NFL trimers, Group B with NFL trimers lacking four N-glycosylation sites at residues 276, 301,360, 463 (del4) and Group C was inoculated twice with the del4 NFL trimers and then boosted with NFL trimers containing all glycans. All vaccines were administered with Matrix-M adjuvant, which was added to the immunogen prior to inoculation. Blood samples were collected two weeks after each vaccine inoculation. MAbs were isolated from the different groups as follows: D11A.B5, D11A.F2, and D11A.F9 (Group A), D15.SF6, D15.SD7 and VD16.2C10 (Group B), D19.PA8, D19.PD8, VD20.1C7, VD20.1F9 and VD20.5A4 (Group C).

# Neutralization assays

Neutralization assays were performed using a single round infectious HIV-1 Env pseudovirus assay with TZM-bl target cells [51]. To determine the mAb concentration or plasma dilution that resulted in a $50\%$ reduction in relative luciferase units (RLU), serial dilutions of the mAbs and the plasma were performed and the neutralization dose-response curves were fit by nonlinear regression using a 5-parameter hill slope equation using the R statistical software

package. Site-directed mutagenesis to generate Env mutants were performed via QuikChange (Agilent Technologies) per the manufacturer's protocol.

# mAb binding analysis by ELISA

NHP mAbs were tested for binding against 16055 gp120 or gp120 V region deletion mutants as previously described [25]. The gp120 deletion mutants include: ΔV1V2 (126–197), ΔV1 (134–153), and ΔV2 (159–193) with residues replaced with GAG or GGSGG for ΔV2. The mAbs were tested for binding using MaxiSorp 96-well plates (Nalgene Nunc International) coated at 2 μg/ml with wt gp120 or gp120 V region deletion mutants in PBS at 4°C overnight. After incubation with blocking buffer (5% non-fat milk/PBS/0.1% Tween-20), the mAbs were added and incubated for 1 hour at 37°C. Binding was detected by secondary HRP-conjugated anti-human Fcγ (Jackson ImmunoResearch) at 1:10,000 for 1 hour. The signal was developed by addition of TMB substrate (Invitrogen) for 5 min, reactions were terminated with 1 N sulfuric acid, and the OD was read at 450 nm. Between each incubation step, the plates were washed six times with PBS containing 0.1% Tween. For cross-competition ELISAs, NHP mAbs were biotinylated using EZ-Link NHS-Biotin (Pierce Biotechnology, Thermo Scientific) per the manufacturer's protocol. 16055 NFL trimers were captured on the ELISA plate by a mouse anti-His tag mAb (R&D Systems) coated at 2 μg/ml in PBS at 4°C overnight. Five-fold serial dilutions of various bNAbs and non-bNAbs were pre-incubated with the captured trimer at RT for 30 min prior to addition of the biotinylated mAbs at a concentration previously determined to give ~75% of the maximum binding signal (i.e. binding to trimer with no competitor present) for 60 min at RT. The bound biotinylated mAbs were detected using HRP-conjugated streptavidin (Sigma) and TMB substrate with the reaction stopped with 1 N sulfuric acid. Competition is expressed as percent inhibition where 0% was the absorbance measured with no inhibitor present.

# Protein expression and purification

Antibodies. All antibodies were expressed in HEK293E cell lines as the expression platform. Cells were grown to a density of 1 million cells/mL and transfected using 293 transfection free reagent (Millipore) mixed with equal ratios of heavy and light chain encoding plasmids with 250 $\mu$ g of DNA per one liter of culture. Expression was allowed to take place for 6 days, rocking at 37°C. Cells were spun down at 4,000 rpm for twenty minutes and the resulting supernatant filtered. For Fab constructs containing a C-terminal His-tag on the heavy chain, supernatants were incubated with Nickel resin (TakaRa) overnight at 4°C, washed with several column volumes of 150 mM NaCl, 5 mM HEPES pH 7.5, and 20 mM Imidazole. The bound protein was eluted with 150 mM NaCl, 5 mM HEPES pH 7.5, and 300 mM Imidazole. IgG constructs were purified by affinity chromatography using GoldBio Protein A resin (GOLD BIO). Following gravity flow, the resin was washed with multiple column volumes of PBS. The bound protein was eluted using IgG elution buffer (Thermo Scientific). Following affinity chromatography, the resulting eluate from Nickel or Protein A resin was further purified by size exclusion chromatography equilibrated in 150 mM NaCl and 5 mM HEPES pH 7.5.

1FD6 scaffold. The 16055 V1V2 1FD6 scaffold was expressed in 293S GNTI $^{-/-}$ cells (Howard Hughes), following the same expression protocol as above. The supernatant was incubated with Nickel resin (TakaRa) overnight at 4°C, washed with several column volumes of 150 mM NaCl, 5 mM HEPES pH 7.5, and 20 mM Imidazole. The bound protein was eluted with 150 mM NaCl, 5 mM HEPES pH 7.5, and 300 mM Imidazole.

16055 NFL. Expression of the 16055 NFL was the same at above. After pelleting the cells, the resulting supernatant was incubated with Galanthus nivalis agglutinin resin (Vector Labs) overnight at 4°C. The resin was washed with 20 mM Tris pH 7.4, 100 mM NaCl, and 1 mM EDTA, and bound protein was eluted with 20 mM Tris, 100 mM NaCl, 1 mM EDTA, 1 mM methylmannopyranoside (MMP), pH 7.4 followed by further purification using SEC.

# Crystallization and X-ray data collection

Structures in complex with the v2b peptide. D11A.B5 and D11A.F2 constructs were mixed with the v2b peptide in a 2:1 peptide to antibody molar ratio and allowed to bind for one hour at room temperature. The complexes were screened against the Hampton Crystal HT, ProPlex HT-96, and Wizard Precipitant Synergy #2 crystallization screens. The NT8 robotic system was used to set initial sitting drop crystallization trials. Following initial hits, crystallization conditions were optimized using hanging drop vapor diffusion. D11A.B5-v2b crystals were grown in 0.1 M Tris pH 8.0 and 1.32 M K/Na Tartrate at 8.5 mg/ml. Crystals were flash frozen in 120% of the crystallization solution supplemented with 15% 2R3R Butanediol. D11A.F2-v2b crystals were grown in 1.7 M Ammonium Sulfate and flash frozen in 2 M Ammonium Sulfate supplemented with 10% 2R3R Butanediol.

D11A.F9 and 35022scFv in complex with the 16055 NFL CC. The D11A.F9 and 35022scFv antibodies were incubated with the 16055 NFL at a three-fold molar excess of antibody. Complex formation occurred for one hour at room temperature. The complex was then treated for 30 minutes at 37°C with the EndoH enzyme. Excess D11A.F9 and 35022scFv were purified away using an SEC column equilibrated in 150 mM NaCl and 5 mM HEPES pH 7.5. Final crystals were grown in 11% PEG 3350, 11% 2-propanol, and 0.1 M Tris pH 8.5, and flash frozen in 120% of the crystallization condition with 15% 2R3R Butanediol.

D15.SD7, D19.PA8 and VD20.5A4 in complex with V1V2-16055 1FD6 scaffold. Typically, about 1.5 mgs of IgG was incubated with 1.5 mgs of 1FD6 scaffold for two hours at room temp before binding to Protein A resin. Unbound scaffold was removed by washing with 150 mM NaCl and 5 mM HEPES pH 7.5. HRV3C enzyme was added to generate Fab: scaffold complexes overnight at 4°C. Following cleavage, the resulting flow through was treated with EndoH for 30 minutes at 37°C and then ran over SEC column equilibrated in 150mM NaCl and 5mM HEPES pH 7.5. Crystals were grown for data collection in the following conditions: The D15.SD7/V1V2-1FD6 crystals were grown in 0.2M Ammonium Sulfate, 0.1M MES pH 6.5, and 22% PEG 8000; D19.PA8/V1V2-1FD6 crystals were grown in 0.1M Tris pH 8.5 and 18% PEG 6000; VD20.5A4-1FD6 crystals were grown in 0.1M Na Acet pH 5.5, 10% w/v PEG 8000, 10% w/v PEG 1000, and 0.2M KSCN. Cryoprotectant solution was incorporated into the crystallization condition prior to crystal freezing.

Structure solution and model building. Data sets were processed using HKL2000, and initial models were generated using molecular replacement in Phenix. The D11A.F2-V2b, D11A.B5-V2b, D15.SD7-V1V2-1FD6 scaffold and D11A.F9 in complex with 16055 NFL and 35022scFv structures all used PDB 4RFO to search for initial molecular replacement solutions. PDB 5UTZ heavy chain and 4CQI light chain were used as molecular replacement search models for the D19.PA8/V1V2-1FD6 complex, and PDB 6U3Z was used as search models for the VD20.5A4-V1V2-1FD6 complex to find molecular replacement solutions. Following molecular replacement, iterative model building and refinement was achieved using COOT and Phenix, respectively.

Summary of crystallization conditions for different complexes obtained.

<table><tr><td>Protein Name</td><td>Concentration</td><td>Crystallization condition</td><td>Synchrotron source</td><td>Resolution</td></tr><tr><td>D11A.F2: v2b peptide</td><td>~8.5 mgs/ml</td><td>1.7 M Ammonium Sulfate.Cryo protection: 2 M Ammonium Sulfate supplemented with 10% 2R3R Butanediol</td><td>ALS 5.0.2</td><td>2.8 Å</td></tr><tr><td>D11A.B5: v2b peptide</td><td>~12.4 mgs/ml</td><td>0.1 M Tris pH 8.0 and 1.32 M K/Na Tartrate at 8.5 mg/ml.Cryo protection: 15% 2R3R Butanediol</td><td>APS ID19</td><td>2.0 Å</td></tr><tr><td>D15.SD7: V1V2-1FD6</td><td>9.8 mgs/ml</td><td>0.2M Ammonium Sulfate, 0.1M MES 6.5, and 22% PEG 8000</td><td>ALS 5.0.1</td><td>2.8 Å</td></tr><tr><td>D19.PA8: V1V2-1FD6</td><td>~10 mgs/ml</td><td>0.1M Tris 8.5, and 18% PEG 6000Cryo protection: 15% 2R3R Butanediol</td><td>APS BM19</td><td>2.0 Å</td></tr><tr><td>VD20.5A4: V1V2-1FD6</td><td>~10 mgs/ml</td><td>0.1M Na Acet 5.5 pH, 10%w/v PEG 8K, 10%w/v PEG 1K, and 0.2M KSCNCryo protection: 20% Ethylene Glycol</td><td>ALS 5.0.1</td><td>2.7 Å</td></tr></table>

https://doi.org/10.1371/journal.ppat.1009543.t001

# Calculation of mAbs' angles of approach

The V2 or V1V2 region from the structures of all antibodies complexes were first superposed onto the V1V2 region (residues 126 and 196 of gp120) of the 16055 NFL trimer (PDB ID: 5UM8). Chimera was used to determine the coordinates of the center of mass (COM) of the 16055 NFL trimer and each Fabs. The angles of approach of each mAbs were determined as follows: for the side angle approach, the X axis, the COM trimer and the COM of each Fab were used while for the angle of approach from the top the Z axis, the COM trimer and the COM of each Fab were used.

# nsEM

Complexes of 16055 NFL CC with three-fold molar excess of antibodies D11A.F9 and 35022scFv were prepared similar to that for crystallization studies. The samples were diluted to $\sim 20~\mu \mathrm{g}~\mathrm{mL}^{-1}$ and applied for $60~s$ to glow discharged Cu grids with continuous carbon film (300 mesh) (Electron Microscopy Sciences). Excess sample was blotted using a Whatman filter paper and stained for an additional $60~s$ using Nano-W (Nanoprobes). Excess liquid was blotted off and the grids air-dried for 1-2 minutes. Data were collected using an FEI Tecnai T12 transmission electron microscope operating at $120\mathrm{keV}$ . Images were taken using a Gatan 4Kx4K charge-coupled device (CCD) at a magnification of 67000X, corresponding to a pixel size of $1.6\AA$ , with exposure time of 1 s and defocus range of -1.0 to $-2.0\mu \mathrm{m}$ . Single-particle EM reconstruction was performed using the Relion software package [52]. Particles were selected from 133 micrographs. CTF correction on the micrographs was carried out within the Relion software suite using CTFFIND [53]. A 4x binned stack of 47973 particles was created and subjected to reference-free 2D classification, and well-defined classes were selected. Selected particle images were then extracted as 2x binned set and subjected to 3D-refinement using a ligand-free structure of HIV Env (BG505.SOSIP) as initial model (PDB ID: 5ACO) [54]. This was followed by 3D classification of the particle images using the final structure from the 3D refinement as initial model. The best classes from 3D classification were grouped together to give a final set of 7685 particles. 3D refinement was performed again on this subset to give a final structure with a resolution of $15.75\AA$ .

# Data and software availability

The crystals diffracted to high resolution at Structural Biology beamlines 5.0.1 and 5.0.2 and Argonne National Laboratory (ANL), Structural Biology Center (SBC) at the Advanced Photon Source (APS). Data reduction and processing were done using HKL2000, scaling with SCALEPACK, and phasing with PHASER using molecular replacement [55]. Model building was completed used Coot [56] and Phenix was utilized for refinement [57]. All structures were

validated using MolProbity [58]. Structure visualization was done with Chimera [59] and PyMOL (The PyMOL Molecular Graphics System, Version 2.0 Schrödinger, LLC.). Figures were created using BioRender (https://app.biorender.com), Prism (GraphPad Prism version 9.0.1 for Mac, GraphPad Software, San Diego, California USA, www.graphpad.com), Chimera [59], and PyMOL (The PyMOL Molecular Graphics System, Version 2.0 Schrödinger, LLC.).

# Supporting information

S1 Fig. (A) Serum neutralization after 2 (post-2) and 3 (post-3) immunization of each animal. Numbers indicate ID50. (B) Cross-competition binding of biotinylated NHP mAbs to 16055 NFL TD CC trimers (His-captured) in the presence of non-biotinylated mAb competitors (left column) as assessed by ELISA. Percent competition was determined based on the absorbance measured with 200 $\mu$ g/ml competitor or 10 $\mu$ g/ml NHP mAbs present and 0% competition being the absorbance measured with no competitor present. (C) Binding of NHP mAbs to 16055 gp120 V loop variants as measured by ELISA: WT, wild-type; $\Delta$ V1V2 ( $\Delta$ 126–197); $\Delta$ V1 ( $\geq\Delta$ 134–153; $\Delta$ V2 ( $\Delta$ 159–193); +, binding; -, no binding. (D) Specificity and relative neutralization potencies of NHP mAbs against a panel of V2 point mutant viruses (residues 182–187 were each mutated to Ala, except for N187Q) compared to wild type. Enhanced potencies as measured by IC50 values are highlighted in red (> 10-fold) and pink (10-fold); decreased potencies in grey, knock-out (KO) mutations in dark grey.
(TIF)

S2 Fig. (A) Side and top view of D11A.F2 Fab (Heavy chain, sky blue; Light chain, cyan) bound to the V2b peptide (yellow) and crystallization artifacts peptide (purple). (B) 2Fo-Fc and Fo-Fc electron density showing clear density for the artefact peptide. (C) Side and top view of D11A.B5 Fab (Heavy chain, magenta; Light chain, light pink) bound to the V2b peptide (yellow) and crystallization artifacts peptide (purple). (D) 2Fo-Fc and Fo-Fc electron density showing clear density for the artefact peptide.
(TIF)

S3 Fig. Superposition of the V2 and V1V2 regions from the crystal structures with the 16055 NFL structure reveals additional contact residues for each mAbs. Side and top view of (A) D11A.B5 (magenta), (B) D15.SD7 (blue), and (C) D19.PA8 (orange) epitopes as defined in the crystal structures; residues showing interactions with the trimer that are not ordered/ included in the crystal structures are shown in black. (D) Sequence of 16055 gp120 listing residues present/ordered in the crystal structures. Residues within $5\AA$ of the mAbs are shown with asterisks underneath the sequence, residues modeled to interact with the trimer that are absent or disordered in the crystal structures are indicated with a grey # while those present in the crystal structures but only show modeled interactions to the trimer are shown in red #. (TIF)

S4 Fig. Epitope comparison between the autologous mAbs antibodies and the broadly neutralizing antibodies. (A) Side and top view surface representation of 16055 NFL (PDB:5UM8) color-coded and labeled as mentioned earlier (Figs 3 and 7). Epitopes targeted by the bNAbs PGT145 (Heavy chain, deepteal; Light chain, light teal)(PDB:5V8L), PG9 (Heavy chain, tv orange; Light chain, wheat)(PDB: 3U2S), PTG122 (Heavy chain, dark gray; Light chain, light gray) and VRC01 (Heavy chain, firebrick; Light chain, light firebrick) (PDB: 5FYK) and our Autologous mAbs (D11A.B5, D15.SD7, D19.PA8, and VD20.5A4) are highlighted and color coded. (B) Side view and (C) Top view superpositions of the bNAbs antibodies structures of PGT145, PG9, PTG122 and VRC01 onto the 16055 NFL trimer, showing how they target their

epitopes. Trimer and mAbs are shown in surface representation. (TIF)

S1 Table. Data collection and refinement statistics for crystal structures. (DOCX)

S2 Table. Detailed interactions of D11A.F2 with 16055 V2b peptide (from PISA web server).
(DOCX)

S3 Table. Detailed interactions of D11A.B5 with 16055 V2b peptide (from PISA web server). (DOCX)

S4 Table. Detailed interactions of D15.SD7 with 16055 V1V2-1FD6 (from PISA web server).
(DOCX)

S5 Table. Detailed interactions of D19.PA8 with 16055 V1V2-1FD6 (from PISA web server).
(DOCX)

S6 Table. Detailed interactions of VD20.5A4 with 16055 V1V2-1FD6 (from PISA web server). (DOCX)

# Acknowledgments

We thank L. Stamatatos for use of laboratory space and equipment, Jason Gorman and Peter D. Kwong for providing the 16055 V1V2-1FD6 scaffold construct, the J. B. Pendleton Charitable Trust for its generous support of Formulatrix robotic instruments and an OctetRED384, Fondation Dormeur, Vaduz for generous support of equipment required for mAb isolation and Novavax, AB, Uppsala, Sweden, for generously making the Matrix-M adjuvant available to do this study. Structural results shown in this study were collected at Structural Biology beamlines 5.0.1 and 5.0.2, which are supported in part by the National Institute of General Medical Sciences, National Institutes of Health. The Advanced Light Source is supported by the Director, Office of Science, Office of Basic Energy Sciences, of the United States Department of Energy under contract number DE-AC02-05CH11231. Also, part of results shown in this report are derived from work performed at Argonne National Laboratory (ANL), Structural Biology Center (SBC) at the Advanced Photon Source (APS), under U.S. Department of Energy, Office of Biological and Environmental Research contract DE-AC02-06CH11357.

# Author Contributions

Conceptualization: Safia S. Aljedani, Tyler J. Liban, Karen Tran, Ganesh Phad, Viktoriya Dubrovskaya, Pradeepa Pushparaj, Paola Martinez-Murillo, Gunilla B. Karlsson Hedestam, Richard T. Wyatt, Marie Pancera.

Formal analysis: Safia S. Aljedani, Karen Tran, Ganesh Phad, Gunilla B. Karlsson Hedestam, Richard T. Wyatt, Marie Pancera.

Funding acquisition: Kelly K. Lee, Gunilla B. Karlsson Hedestam, Richard T. Wyatt, Marie Pancera.

Investigation: Safia S. Aljedani, Tyler J. Liban, Karen Tran, Ganesh Phad, Vidya Mangala Prasad, Gunilla B. Karlsson Hedestam, Richard T. Wyatt, Marie Pancera.

Methodology: Safia S. Aljedani, Tyler J. Liban, Karen Tran, Ganesh Phad, Suruchi Singh, Viktoriya Dubrovskaya, Pradeepa Pushparaj, Paola Martinez-Murillo, Justas Rodarte, Alex Mileant, Vidya Mangala Prasad, Rachel Kinzelman, Sijy O'Dell, Marie Pancera.

Supervision: John R. Mascola, Kelly K. Lee, Gunilla B. Karlsson Hedestam, Richard T. Wyatt, Marie Pancera.

Writing - original draft: Safia S. Aljedani, Marie Pancera.

Writing – review & editing: Safia S. Aljedani, Tyler J. Liban, Karen Tran, Gunilla B. Karlsson Hedestam, Richard T. Wyatt, Marie Pancera.

# References

1. Gartner MJ, Roche M, Churchill MJ, Gorry PR, Flynn JK. Understanding the mechanisms driving the spread of subtype C HIV-1. EBioMedicine. 2020; 53:102682. Epub 2020/03/03. https://doi.org/10.1016/j.ebiom.2020.102682 PMID: 32114391; PubMed Central PMCID: PMC7047180.   
2. UNAIDS. Executive summary —2020 Global AIDS Update —Seizing the moment —Tackling entrenched inequalities to end epidemics 2020. Available from: https://www.unaids.org/en/resources/documents/2020/2020_global-aids-report_executive-summary.   
3. Robertson DL, Anderson JP, Bradac JA, Carr JK, Foley B, Funkhouser RK, et al. HIV-1 nomenclature proposal. Science. 2000; 288(5463):55–6. Epub 2000/04/15. https://doi.org/10.1126/science.288.5463.55d PMID: 10766634.   
4. Taylor BS, Sobieszczyk ME, McCutchan FE, Hammer SM. The challenge of HIV-1 subtype diversity. N Engl J Med. 2008; 358(15):1590–602. Epub 2008/04/12. https://doi.org/10.1056/NEJMra0706737 PMID: 18403767; PubMed Central PMCID: PMC2614444.   
5. Fonjungo PN, Mpoudi EN, Torimiro JN, Alemnji GA, Eno LT, Lyonga EJ, et al. Human immunodeficiency virus type 1 group m protease in cameroon: genetic diversity and protease inhibitor mutational features. J Clin Microbiol. 2002; 40(3):837–45. Epub 2002/03/07. https://doi.org/10.1128/JCM.40.3.837-845.2002 PMID: 11880402; PubMed Central PMCID: PMC120267.   
6. Wyatt R, Sodroski J. The HIV-1 envelope glycoproteins: fusogens, antigens, and immunogens. Science. 1998; 280(5371):1884–8. Epub 1998/06/25. https://doi.org/10.1126/science.280.5371.1884 PMID: 9632381.   
7. Seabright GE, Doores KJ, Burton DR, Crispin M. Protein and Glycan Mimicry in HIV Vaccine Design. J Mol Biol. 2019; 431(12):2223–47. Epub 2019/04/28. https://doi.org/10.1016/j.jmb.2019.04.016 PMID: 31028779; PubMed Central PMCID: PMC6556556.   
8. Kwong PD, Mascola JR. HIV-1 Vaccines Based on Antibody Identification, B Cell Ontogeny, and Epitope Structure. Immunity. 2018; 48(5):855–71. Epub 2018/05/17. https://doi.org/10.1016/j.immuni.2018.04.029 PMID: 29768174.   
9. West AP Jr., Scharf L, Scheid JF, Klein F, Bjorkman PJ, Nussenzweig MC. Structural insights on the role of antibodies in HIV-1 vaccine and therapy. Cell. 2014; 156(4):633–48. Epub 2014/02/18. https://doi.org/10.1016/j.cell.2014.01.052 PMID: 24529371; PubMed Central PMCID: PMC4041625.   
10. Joyce MG, Kanekiyo M, Xu L, Biertumpfel C, Boyington JC, Moquin S, et al. Outer domain of HIV-1 gp120: antigenic optimization, structural malleability, and crystal structure with antibody VRC-PG04. J Virol. 2013; 87(4):2294–306. Epub 2012/12/14. https://doi.org/10.1128/JVI.02717-12 PMID: 23236069; PubMed Central PMCID: PMC3571475.   
11. Karlsson Hedestam GB, Guenaga J, Corcoran M, Wyatt RT. Evolution of B cell analysis and Env trimer redesign. Immunol Rev. 2017; 275(1):183–202. Epub 2017/01/31. https://doi.org/10.1111/imr.12515 PMID: 28133805; PubMed Central PMCID: PMC5301504.   
12. Li Y, O'Dell S, Walker LM, Wu X, Guenaga J, Feng Y, et al. Mechanism of neutralization by the broadly neutralizing HIV-1 monoclonal antibody VRC01. J Virol. 2011; 85(17):8954–67. Epub 2011/07/01. https://doi.org/10.1128/JVI.00754-11 PMID: 21715490; PubMed Central PMCID: PMC3165784.   
13. Wei X, Decker JM, Wang S, Hui H, Kappes JC, Wu X, et al. Antibody neutralization and escape by HIV-1. Nature. 2003; 422(6929):307–12. Epub 2003/03/21. https://doi.org/10.1038/nature01470 PMID: 12646921.

14. Lynch RM, Rong R, Boliar S, Sethi A, Li B, Mulenga J, et al. The B cell response is redundant and highly focused on V1V2 during early subtype C infection in a Zambian seroconverter. J Virol. 2011; 85(2):905–15. Epub 2010/10/29. https://doi.org/10.1128/JVI.02006-10 PMID: 20980495; PubMed Central PMCID: PMC3020014.   
15. Sivay MV, Hudelson SE, Wang J, Agyei Y, Hamilton EL, Selin A, et al. HIV-1 diversity among young women in rural South Africa: HPTN 068. PLoS One. 2018; 13(7):e0198999. Epub 2018/07/06. https://doi.org/10.1371/journal.pone.0198999 PMID: 29975689; PubMed Central PMCID: PMC6033411.   
16. Burton S, Spicer LM, Charles TP, Gangadhara S, Reddy PBJ, Styles TM, et al. Clade C HIV-1 Envelope Vaccination Regimens Differ in Their Ability To Elicit Antibodies with Moderate Neutralization Breadth against Genetically Diverse Tier 2 HIV-1 Envelope Variants. J Virol. 2019; 93(7). Epub 2019/01/18. https://doi.org/10.1128/JVI.01846-18 PMID: 30651354; PubMed Central PMCID: PMC6430525.   
17. Wang Q, Ma B, Liang Q, Zhu A, Wang H, Fu L, et al. Stabilized diverse HIV-1 envelope trimers for vaccine design. Emerg Microbes Infect. 2020; 9(1):775–86. Epub 2020/04/04. https://doi.org/10.1080/22221751.2020.1745093 PMID: 32241249; PubMed Central PMCID: PMC7178897.   
18. Guenaga J, Dubrovskaya V, de Val N, Sharma SK, Carrette B, Ward AB, et al. Structure-Guided Redesign Increases the Propensity of HIV Env To Generate Highly Stable Soluble Trimers. J Virol. 2015; 90(6):2806–17. Epub 2016/01/01. https://doi.org/10.1128/JVI.02652-15 PMID: 26719252; PubMed Central PMCID: PMC4810649.   
19. Guenaga J, Garces F, de Val N, Stanfield RL, Dubrovskaya V, Higgins B, et al. Glycine Substitution at Helix-to-Coil Transitions Facilitates the Structural Determination of a Stabilized Subtype C HIV Envelope Glycoprotein. Immunity. 2017; 46(5):792–803 e3. Epub 2017/05/18. https://doi.org/10.1016/j.immuni.2017.04.014 PMID: 28514686; PubMed Central PMCID: PMC5439057.   
20. Chuang GY, Geng H, Pancera M, Xu K, Cheng C, Acharya P, et al. Structure-Based Design of a Soluble Prefusion-Closed HIV-1 Env Trimer with Reduced CD4 Affinity and Improved Immunogenicity. J Virol. 2017; 91(10). Epub 2017/03/10. https://doi.org/10.1128/JVI.02268-16 PMID: 28275193; PubMed Central PMCID: PMC5411596.   
21. Sanders RW, Derking R, Cupo A, Julien JP, Yasmeen A, de Val N, et al. A next-generation cleaved, soluble HIV-1 Env trimer, BG505 SOSIP.664 gp140, expresses multiple epitopes for broadly neutralizing but not non-neutralizing antibodies. PLoS Pathog. 2013; 9(9):e1003618. Epub 2013/09/27. https://doi.org/10.1371/journal.ppat.1003618 PMID: 24068931; PubMed Central PMCID: PMC3777863.   
22. Rutten L, Lai YT, Blokland S, Truan D, Bisschop IJM, Strokappe NM, et al. A Universal Approach to Optimize the Folding and Stability of Prefusion-Closed HIV-1 Envelope Trimers. Cell Rep. 2018; 23(2):584–95. Epub 2018/04/12. https://doi.org/10.1016/j.celrep.2018.03.061 PMID: 29642014; PubMed Central PMCID: PMC6010203.   
23. Pancera M, Zhou T, Druz A, Georgiev IS, Soto C, Gorman J, et al. Structure and immune recognition of trimeric pre-fusion HIV-1 Env. Nature. 2014; 514(7523):455–61. Epub 2014/10/09. https://doi.org/10.1038/nature13808 PMID: 25296255; PubMed Central PMCID: PMC4348022.   
24. Dubrovskaya V, Tran K, Ozorowski G, Guenaga J, Wilson R, Bale S, et al. Vaccination with Glycan-Modified HIV NFL Envelope Trimer-Liposomes Elicits Broadly Neutralizing Antibodies to Multiple Sites of Vulnerability. Immunity. 2019; 51(5):915–29 e7. Epub 2019/11/17. https://doi.org/10.1016/j.immuni.2019.10.008 PMID: 31732167; PubMed Central PMCID: PMC6891888.   
25. Martinez-Murillo P, Tran K, Guenaga J, Lindgren G, Adori M, Feng Y, et al. Particulate Array of Well-Ordered HIV Clade C Env Trimers Elicits Neutralizing Antibodies that Display a Unique V2 Cap Approach. Immunity. 2017; 46(5):804–17 e7. Epub 2017/05/18. https://doi.org/10.1016/j.immuni.2017.04.021 PMID: 28514687; PubMed Central PMCID: PMC5528178.   
26. Phad GE, Pushparaj P, Tran K, Dubrovskaya V, Adori M, Martinez-Murillo P, et al. Extensive dissemination and intraclonal maturation of HIV Env vaccine-induced B cell responses. J Exp Med. 2020; 217(2). Epub 2019/11/11. https://doi.org/10.1084/jem.20191155 PMID: 31704807; PubMed Central PMCID: PMC7041718.   
27. Vazquez Bernat N, Corcoran M, Nowak I, Kaduk M, Castro Dopico X, Narang S, et al. Rhesus and cynomolgus macaque immunoglobulin heavy-chain genotyping yields comprehensive databases of germline VDJ alleles. Immunity. 2021; 54(2):355–66 e4. Epub 2021/01/24. https://doi.org/10.1016/j.immuni.2020.12.018 PMID: 33484642.   
28. Kwong PD, Wyatt R, Desjardins E, Robinson J, Culp JS, Hellmig BD, et al. Probability analysis of variational crystallization and its application to gp120, the exterior envelope glycoprotein of type 1 human immunodeficiency virus (HIV-1). J Biol Chem. 1999; 274(7):4115–23. Epub 1999/02/06. https://doi.org/10.1074/jbc.274.7.4115 PMID: 9933605.   
29. McLellan JS, Pancera M, Carrico C, Gorman J, Julien JP, Khayat R, et al. Structure of HIV-1 gp120 V1/V2 domain with broadly neutralizing antibody PG9. Nature. 2011; 480(7377):336–43. Epub 2011/11/25. https://doi.org/10.1038/nature10696 PMID: 22113616; PubMed Central PMCID: PMC3406929.

30. Huang J, Kang BH, Pancera M, Lee JH, Tong T, Feng Y, et al. Broad and potent HIV-1 neutralization by a human antibody that binds the gp41-gp120 interface. Nature. 2014; 515(7525):138–42. Epub 2014/09/05. https://doi.org/10.1038/nature13601 PMID: 25186731; PubMed Central PMCID: PMC4224615.   
31. Yang L, Sharma SK, Cottrell C, Guenaga J, Tran K, Wilson R, et al. Structure-Guided Redesign Improves NFL HIV Env Trimer Integrity and Identifies an Inter-Protomer Disulfide Permitting Post-Expression Cleavage. Front Immunol. 2018; 9:1631. Epub 2018/08/02. https://doi.org/10.3389/fimmu.2018.01631 PMID: 30065725; PubMed Central PMCID: PMC6056610.   
32. Lai YT, Wang T, O'Dell S, Louder MK, Schon A, Cheung CSF, et al. Lattice engineering enables definition of molecular features allowing for potent small-molecule inhibition of HIV-1 entry. Nat Commun. 2019; 10(1):47. Epub 2019/01/04. https://doi.org/10.1038/s41467-018-07851-1 PMID: 30604750; PubMed Central PMCID: PMC6318274.   
33. Korber B, Foley B. T., Kuiken C., Pillai S. K., & Sodroski J. G. Numbering positions in HIV relative to HXB2CG. Human retroviruses and AIDS, 3, 102–111. 1998.   
34. Flyak AI, Ruiz S, Colbert MD, Luong T, Crowe JE Jr., Bailey JR, et al. HCV Broadly Neutralizing Antibodies Use a CDRH3 Disulfide Motif to Recognize an E2 Glycoprotein Site that Can Be Targeted for Vaccine Design. Cell Host Microbe. 2018; 24(5):703–16 e3. Epub 2018/11/16. https://doi.org/10.1016/j.chom.2018.10.009 PMID: 30439340; PubMed Central PMCID: PMC6258177.   
35. Doria-Rose NA, Schramm CA, Gorman J, Moore PL, Bhiman JN, DeKosky BJ, et al. Developmental pathway for potent V1V2-directed HIV-neutralizing antibodies. Nature. 2014; 509(7498):55–62. Epub 2014/03/05. https://doi.org/10.1038/nature13036 PMID: 24590074; PubMed Central PMCID: PMC4395007.   
36. Dolinsky TJ, Nielsen JE, McCammon JA, Baker NA. PDB2PQR: an automated pipeline for the setup of Poisson-Boltzmann electrostatics calculations. Nucleic Acids Res. 2004; 32(Web Server issue):W665–7. Epub 2004/06/25. https://doi.org/10.1093/nar/gkh381 PMID: 15215472; PubMed Central PMCID: PMC441519.   
37. Berndsen ZT, Chakraborty S, Wang X, Cottrell CA, Torres JL, Diedrich JK, et al. Visualization of the HIV-1 Env glycan shield across scales. Proc Natl Acad Sci U S A. 2020. Epub 2020/10/24. https://doi.org/10.1073/pnas.2000260117 PMID: 33093196.   
38. Dubrovskaya V, Guenaga J, de Val N, Wilson R, Feng Y, Movsesyan A, et al. Targeted N-glycan deletion at the receptor-binding site retains HIV Env NFL trimer integrity and accelerates the elicited antibody response. PLoS Pathog. 2017; 13(9):e1006614. Epub 2017/09/14. https://doi.org/10.1371/journal.ppat.1006614 PMID: 28902916; PubMed Central PMCID: PMC5640423.   
39. Ingale J, Tran K, Kong L, Dey B, McKee K, Schief W, et al. Hyperglycosylated stable core immunogens designed to present the CD4 binding site are preferentially recognized by broadly neutralizing antibodies. J Virol. 2014; 88(24):14002–16. Epub 2014/09/26. https://doi.org/10.1128/JVI.02614-14 PMID: 25253346; PubMed Central PMCID: PMC4249138.   
40. Pritchard LK, Spencer DI, Royle L, Bonomelli C, Seabright GE, Behrens AJ, et al. Glycan clustering stabilizes the mannose patch of HIV-1 and preserves vulnerability to broadly neutralizing antibodies. Nat Commun. 2015; 6:7479. Epub 2015/06/25. https://doi.org/10.1038/ncomms8479 PMID: 26105115; PubMed Central PMCID: PMC4500839.   
41. Burton DR, Mascola JR. Antibody responses to envelope glycoproteins in HIV-1 infection. Nat Immunol. 2015; 16(6):571–6. Epub 2015/05/20. https://doi.org/10.1038/ni.3158 PMID: 25988889; PubMed Central PMCID: PMC4834917.   
42. Mascola JR, Montefiori DC. The role of antibodies in HIV vaccines. Annu Rev Immunol. 2010; 28:413–44. Epub 2010/03/03. https://doi.org/10.1146/annurev-immunol-030409-101256 PMID: 20192810.   
43. Brouwer PJM, Antanasijevic A, de Gast M, Allen JD, Bijl TPL, Yasmeen A, et al. Immunofocusing and enhancing autologous Tier-2 HIV-1 neutralization by displaying Env trimers on two-component protein nanoparticles. NPJ Vaccines. 2021; 6(1):24. Epub 2021/02/11. https://doi.org/10.1038/s41541-021-00285-9 PMID: 33563983; PubMed Central PMCID: PMC7873233.   
44. Burton DR, Hangartner L. Broadly Neutralizing Antibodies to HIV and Their Role in Vaccine Design. Annu Rev Immunol. 2016; 34:635–59. Epub 2016/05/12. https://doi.org/10.1146/annurev-immunol-041015-055515 PMID: 27168247; PubMed Central PMCID: PMC6034635.   
45. Yang YR, McCoy LE, van Gils MJ, Andrabi R, Turner HL, Yuan M, et al. Autologous Antibody Responses to an HIV Envelope Glycan Hole Are Not Easily Broadened in Rabbits. J Virol. 2020; 94(7). Epub 2020/01/17. https://doi.org/10.1128/JVI.01861-19 PMID: 31941772; PubMed Central PMCID: PMC7081899.   
46. McCoy LE, van Gils MJ, Ozorowski G, Messmer T, Briney B, Voss JE, et al. Holes in the Glycan Shield of the Native HIV Envelope Are a Target of Trimer-Elicited Neutralizing Antibodies. Cell Rep. 2016; 16(9):2327–38. Epub 2016/08/23. https://doi.org/10.1016/j.celrep.2016.07.074 PMID: 27545891; PubMed Central PMCID: PMC5007210.

47. Hessell AJ, Powell R, Jiang X, Luo C, Weiss S, Dussupt V, et al. Multimeric Epitope-Scaffold HIV Vaccines Target V1V2 and Differentially Tune Polyfunctional Antibody Responses. Cell Rep. 2019; 28(4):877–95 e6. Epub 2019/07/25. https://doi.org/10.1016/j.celrep.2019.06.074 PMID: 31340151; PubMed Central PMCID: PMC6666430.   
48. Powell RL, Weiss S, Fox A, Liu X, Itri V, Jiang X, et al. An HIV Vaccine Targeting the V2 Region of the HIV Envelope Induces a Highly Durable Polyfunctional Fc-Mediated Antibody Response in Rhesus Macaques. J Virol. 2020; 94(17). Epub 2020/06/20. https://doi.org/10.1128/JVI.01175-20 PMID: 32554699; PubMed Central PMCID: PMC7431793.   
49. Gorny MK, Pan R, Williams C, Wang XH, Volsky B, O'Neal T, et al. Functional and immunochemical cross-reactivity of V2-specific monoclonal antibodies from HIV-1-infected individuals. Virology. 2012;427(2):198–207. Epub 2012/03/10. https://doi.org/10.1016/j.virol.2012.02.003 PMID: 22402248; PubMed Central PMCID: PMC3572902.   
50. Wibmer CK, Richardson SI, Yolitz J, Cicala C, Arthos J, Moore PL, et al. Common helical V1V2 conformations of HIV-1 Envelope expose the alpha4beta7 binding site on intact virions. Nat Commun. 2018; 9(1):4489. Epub 2018/10/28. https://doi.org/10.1038/s41467-018-06794-x PMID: 30367034; PubMed Central PMCID: PMC6203816.   
51. Li M, Gao F, Mascola JR, Stamatatos L, Polonis VR, Koutsoukos M, et al. Human immunodeficiency virus type 1 env clones from acute and early subtype B infections for standardized assessments of vaccine-elicited neutralizing antibodies. J Virol. 2005; 79(16):10108–25. Epub 2005/07/30. https://doi.org/10.1128/JVI.79.16.10108-10125.2005 PMID: 16051804; PubMed Central PMCID: PMC1182643.   
52. Scheres SH. RELION: implementation of a Bayesian approach to cryo-EM structure determination. J Struct Biol. 2012; 180(3):519–30. Epub 2012/09/25. https://doi.org/10.1016/j.jsb.2012.09.006 PMID: 23000701; PubMed Central PMCID: PMC3690530.   
53. Rohou A, Grigorieff N. CTFFIND4: Fast and accurate defocus estimation from electron micrographs. J Struct Biol. 2015; 192(2):216–21. Epub 2015/08/19. https://doi.org/10.1016/j.jsb.2015.08.008 PMID: 26278980; PubMed Central PMCID: PMC6760662.   
54. Lee JH, de Val N, Lyumkis D, Ward AB. Model Building and Refinement of a Natively Glycosylated HIV-1 Env Protein by High-Resolution Cryoelectron Microscopy. Structure. 2015; 23(10):1943–51. Epub 2015/09/22. https://doi.org/10.1016/j.str.2015.07.020 PMID: 26388028; PubMed Central PMCID: PMC4618500.   
55. Bunkoczi G, Echols N, McCoy AJ, Oeffner RD, Adams PD, Read RJ. Phaser.MRage: automated molecular replacement. Acta Crystallogr D Biol Crystallogr. 2013; 69(Pt 11):2276–86. Epub 2013/11/06. https://doi.org/10.1107/S0907444913022750 PMID: 24189240; PubMed Central PMCID: PMC3817702.   
56. Emsley P, Cowtan K. Coot: model-building tools for molecular graphics. Acta Crystallogr D Biol Crystallogr. 2004; 60(Pt 12 Pt 1):2126–32. Epub 2004/12/02. https://doi.org/10.1107/S0907444904019158 PMID: 15572765.   
57. Adams PD, Afonine PV, Bunkoczi G, Chen VB, Davis IW, Echols N, et al. PHENIX: a comprehensive Python-based system for macromolecular structure solution. Acta Crystallogr D Biol Crystallogr. 2010;66(Pt 2):213–21. Epub 2010/02/04. https://doi.org/10.1107/S0907444909052925 PMID: 20124702;PubMed Central PMCID: PMC2815670.   
58. Williams CJ, Headd JJ, Moriarty NW, Prisant MG, Videau LL, Deis LN, et al. MolProbity: More and better reference data for improved all-atom structure validation. Protein Sci. 2018; 27(1):293–315. Epub 2017/10/27. https://doi.org/10.1002/pro.3330 PMID: 29067766; PubMed Central PMCID: PMC5734394.   
59. Pettersen EF, Goddard TD, Huang CC, Couch GS, Greenblatt DM, Meng EC, et al. UCSF Chimera—a visualization system for exploratory research and analysis. J Comput Chem. 2004; 25(13):1605–12. Epub 2004/07/21. https://doi.org/10.1002/jcc.20084 PMID: 15264254.